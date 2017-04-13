from __future__ import print_function

import copy
import time
import warnings

program_start_time = time.time()
warnings.simplefilter("ignore", UserWarning)  # cuDNN warning

import logging
import formatting

logger_evaluate = logging.getLogger('evaluate')
logger_evaluate.setLevel(logging.INFO)
FORMAT = '[$BOLD%(filename)s$RESET:%(lineno)d][%(levelname)-5s]: %(message)s '
formatter = logging.Formatter(formatting.formatter_message(FORMAT, False))
formatter2 = logging.Formatter('%(asctime)s - %(name)-5s - %(levelname)-10s - (%(filename)s:%(lineno)d): %(message)s')

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger_evaluate.addHandler(ch)

print("\n * Importing libraries...")
from RNN_tools_lstm import *
import general_tools
import preprocessWavs
import fixDataset.transform as transform
from readData import *



class modelEvaluator:
    def __init__(self, model_dataset="combined"):
        ###########################

        # network parameters
        nbMFCCs = 39 # num of features to use -> see 'utils.py' in convertToPkl under processDatabase
        nbPhonemes = 39
        N_HIDDEN_LIST = [32, 32, 32, 32, 32, 32, 32, 32]
        BIDIRECTIONAL = True
        ADD_DENSE_LAYERS = False
        batch_size = 32

        # MODEL and log locations
        self.model_dataset = model_dataset # model_datast = "TCDTIMIT"  # the dataset the model has been trained on
        model_dir = os.path.expanduser("~/TCDTIMIT/audioSR/" + model_dataset + "/results/")
        meanStd_path = os.path.expanduser(
            "~/TCDTIMIT/audioSR/" + model_dataset + "/binary39/" + model_dataset + "MeanStd.pkl")
        store_dir = os.path.expanduser("~/TCDTIMIT/audioSR/" + model_dataset + "/evaluations")

        # where preprocessed data will be stored in PKL format
        data_store_dir = os.path.expanduser("~/TCDTIMIT/audioSR/dataPreparedForEvaluation/batch_size32/")

        # get all the wavDirs'
        evaluate_datasets = ['TIMIT','TCDTIMIT']
        dataNames = ['/TEST']#,'/TRAIN']


        #################
        # locations for LOG, PARAMETERS, TRAIN info (automatically generated)
        model_name = str(len(N_HIDDEN_LIST)) + "_LSTMLayer" + '_'.join([str(layer) for layer in N_HIDDEN_LIST]) \
                     + "_nbMFCC" + str(nbMFCCs) + (
                         "_bidirectional" if BIDIRECTIONAL else "_unidirectional") + (
        "_withDenseLayers" if ADD_DENSE_LAYERS else "") + "_" + model_dataset

        store_dir = store_dir + os.sep + model_name
        if not os.path.exists(store_dir): os.makedirs(store_dir)
        # model parameters and network_training_info
        model_load = os.path.join(model_dir, model_name + ".npz")

        #### BUIDING MODEL ####
        logger_evaluate.info('* Building network ...')
        self.RNN_network = NeuralNetwork('RNN', batch_size=batch_size, num_features=nbMFCCs, n_hidden_list=N_HIDDEN_LIST,
                                    num_output_units=nbPhonemes, bidirectional=BIDIRECTIONAL, addDenseLayers=ADD_DENSE_LAYERS, seed=0,
                                    logger=logger_evaluate)
        # Try to load stored model
        logger_evaluate.info(' Network built. Trying to load stored model: %s', model_load)
        self.RNN_network.load_model(model_load, logger=logger_evaluate)

        # print number of parameters
        nb_params = lasagne.layers.count_params(self.RNN_network.network_output_layer)
        logger_evaluate.info(" Number of parameters of this network: %s", nb_params )

        ##### COMPILING FUNCTIONS #####
        logger_evaluate.info("* Compiling functions ...")
        self.RNN_network.build_functions(debug=False, train=False, logger=logger_evaluate)
        self.validate_fn = self.RNN_network.validate_fn
        self.predictions_fn = self.RNN_network.predictions_fn


        ## EVALUATION TIME ##
        # loop over the train/test test of the different datasets
        for evaluate_dataset in evaluate_datasets:
            for dataName in dataNames:
                wavDir = os.path.expanduser("~/TCDTIMIT/audioSR/" + evaluate_dataset + "/fixed39/") \
                         + evaluate_dataset + dataName
                dataName = evaluate_dataset + dataName
                self.evaluateModel(BIDIRECTIONAL, N_HIDDEN_LIST, batch_size, dataName, wavDir, data_store_dir, meanStd_path, model_load,
                                 nbMFCCs, store_dir, force_overwrite=True)

        # # evaluate TCDTIMIT lipspeakers
        # dataName = 'TCDTIMIT/lipspeakers'
        # # lipspeakers = 'TCDTIMIT/lipspeakers'
        # # Lipspkr1 = 'TCDTIMIT/lipspeakers/Lipspkr1'
        # # volunteers = 'TCDTIMIT/volunteers'
        # # volunteer10M = 'TCDTIMIT/volunteers/10M'
        # wavDir = os.path.expanduser('~/TCDTIMIT/audioSR/TCDTIMIT/fixed39_nonSplit/TCDTIMIT/lipspeakers')
        # self.evaluateModel(BIDIRECTIONAL, N_HIDDEN_LIST, batch_size, dataName, wavDir, data_store_dir, meanStd_path,
        #                    model_load, nbMFCCs, store_dir, force_overwrite=True)


    def evaluateModel(self, BIDIRECTIONAL, N_HIDDEN_LIST, batch_size, dataName, wavDir, data_store_dir, meanStd_path, model_load,
                    nbMFCCs, store_dir, force_overwrite=False):
        logger_evaluate.info("\n\n\n")

        #TODO: if evaluation file already exists, do nothing
        ####### THE DATA you want to evaluate ##########
        # dataName = dataName.lstrip("/")
        data_store_path = data_store_dir + dataName.replace('/', '_') + "_nbMFCC" + str(nbMFCCs)
        if not os.path.exists(data_store_dir): os.makedirs(data_store_dir)
        predictions_path = store_dir + os.sep + dataName.replace('/', '_') + "_predictions.pkl"

        # log file
        logFile = store_dir + os.sep + "Evaluation" + dataName.replace('/', '_') + '.log'
        if os.path.exists(logFile) and not force_overwrite:
            from general_tools import query_yes_no
            if query_yes_no("Log file already exists at %s\n Do you want to evaluate again and overwrite?","y"):
                pass
            else:
                logger_evaluate.info("Log file already exists, not re-evaluating.... ")
                return 0
        fh = logging.FileHandler(logFile, 'w')  # create new logFile
        fh.setLevel(logging.INFO)
        fh.setFormatter(formatter)
        logger_evaluate.addHandler(fh)
        logger_evaluate.info("\n  MODEL:    %s", model_load)
        logger_evaluate.info("\n  WAV_DIR:  %s", wavDir)
        logger_evaluate.info("\n  PREDICTS: %s", predictions_path)
        logger_evaluate.info("\n  LOG:      %s", logFile)
        logger_evaluate.info("\n")

        # GATHERING DATA
        logger_evaluate.info("* Gathering Data ...")
        if os.path.exists(data_store_path + ".pkl"):
            [inputs, targets, valid_frames] = unpickle(data_store_path + ".pkl")
            calculateAccuracy = True
            logger_evaluate.info("Successfully loaded preprocessed data, with targets")
        elif os.path.exists(data_store_path + "_noTargets.pkl"):
            [inputs] = unpickle(data_store_path + "_noTargets.pkl")
            calculateAccuracy = False
            logger_evaluate.info("Successfully loaded preprocessed data, no targets")
        else:
            logger_evaluate.info("Data not found, preprocessing...")

            # From WAVS, generate X, y and valid_frames; also store under data_store_dir
            def preprocessLabeledWavs(wavDir, store_dir, name):
                # fixWavs -> suppose this is done
                # convert to pkl
                X, y, valid_frames = preprocessWavs.preprocess_dataset(source_path=wavDir, nbMFCCs=nbMFCCs,logger=logger_evaluate)

                X_data_type = 'float32'
                X = preprocessWavs.set_type(X, X_data_type)
                y_data_type = 'int32'
                y = preprocessWavs.set_type(y, y_data_type)
                valid_frames_data_type = 'int32'
                valid_frames = preprocessWavs.set_type(valid_frames, valid_frames_data_type)

                return X, y, valid_frames

            def preprocessUnlabeledWavs(wavDir, store_dir, name):
                # fixWavs -> suppose this is done
                # convert to pkl
                X = preprocessWavs.preprocess_unlabeled_dataset(source_path=wavDir, nbMFCCs=nbMFCCs, logger=logger_evaluate)

                X_data_type = 'float32'
                X = preprocessWavs.set_type(X, X_data_type)

                return X

            wav_files = transform.loadWavs(wavDir)
            wav_filenames = [str(
                    os.path.basename(
                        os.path.dirname(os.path.dirname(os.path.dirname(wav_file)))) + os.sep + os.path.basename(
                            os.path.dirname(os.path.dirname(wav_file))) + os.sep + os.path.basename(
                            os.path.dirname(wav_file)) + os.sep + os.path.basename(wav_file)) for wav_file in wav_files]
            logger_evaluate.info("Found %s files to evaluate \n Example: %s", len(wav_filenames), wav_filenames[0])
            label_files = transform.loadPhns(wavDir)

            # if source dir doesn't contain labelfiles, we can't calculate accuracy
            calculateAccuracy = True
            if not (len(wav_files) == len(label_files)):
                calculateAccuracy = False
                inputs = preprocessUnlabeledWavs(wavDir=wavDir, store_dir=store_dir, name=dataName)
            else:
                inputs, targets, valid_frames = preprocessLabeledWavs(wavDir=wavDir, store_dir=store_dir, name=dataName)

            # normalize inputs, convert to float32
            with open(meanStd_path, 'rb') as cPickle_file:
                [mean_val, std_val] = cPickle.load(cPickle_file)
            inputs = preprocessWavs.normalize(inputs, mean_val, std_val)

            # just to be sure
            X_data_type = 'float32'
            inputs = preprocessWavs.set_type(inputs, X_data_type)

            # Print some information
            logger_evaluate.debug("* Data information")
            logger_evaluate.debug('  inputs')
            logger_evaluate.debug('%s %s', type(inputs), len(inputs))
            logger_evaluate.debug('%s %s', type(inputs[0]), inputs[0].shape)
            logger_evaluate.debug('%s %s', type(inputs[0][0]), inputs[0][0].shape)
            logger_evaluate.debug('%s', type(inputs[0][0][0]))
            logger_evaluate.debug('y train')
            logger_evaluate.debug('  %s %s', type(targets), len(targets))
            logger_evaluate.debug('  %s %s', type(targets[0]), targets[0].shape)
            logger_evaluate.debug('  %s %s', type(targets[0][0]), targets[0][0].shape)

            # slice to have a #inputs that is a multiple of batch size
            logger_evaluate.info("Not evaluating %s last files (batch size mismatch)", len(inputs) % batch_size)
            inputs = inputs[:-(len(inputs) % batch_size) or None]
            if calculateAccuracy:
                targets = targets[:-(len(targets) % batch_size) or None]
                valid_frames = valid_frames[:-(len(valid_frames) % batch_size) or None]

            # pad the inputs to process batches easily
            inputs = pad_sequences_X(inputs)
            if calculateAccuracy: targets = pad_sequences_y(targets)

            # save the processed data
            logger_evaluate.info("storing preprocessed data to: %s", data_store_path)
            if calculateAccuracy:
                general_tools.saveToPkl(data_store_path + '.pkl', [inputs, targets, valid_frames])
            else:
                general_tools.saveToPkl(data_store_path + '_noTargets.pkl', [inputs])

        # Gather filenames for debugging
        wav_files = transform.loadWavs(wavDir)
        wav_filenames = [str(
                os.path.basename(
                    os.path.dirname(os.path.dirname(os.path.dirname(wav_file)))) + os.sep + os.path.basename(
                        os.path.dirname(os.path.dirname(wav_file))) + os.sep + os.path.basename(
                        os.path.dirname(wav_file)) + os.sep + os.path.basename(wav_file)) for wav_file in wav_files]
        logger_evaluate.debug(" # inputs: %s, # wav files: %s", len(inputs), len(wav_files))
        # make copy of data because we might need to use is again for calculating accurasy, and the iterator will remove elements from the array
        inputs_bak = copy.deepcopy(inputs)
        if calculateAccuracy:
            targets_bak = copy.deepcopy(targets)
            valid_frames_bak = copy.deepcopy(valid_frames)
        logger_evaluate.info("* Evaluating: pass over Evaluation Set")
        predictions = []
        if calculateAccuracy:
            # if .phn files are provided, we can check our predictions
            totError = 0
            totAcc = 0
            n_batches = 0
            logger_evaluate.info("Getting predictions and calculating accuracy...")
            inputs_padded = []
            targets_padded = []
            for input_batch, target_batch, mask_batch, seq_length_batch in tqdm(
                    iterate_minibatches(inputs, targets, valid_frames,
                                        batch_size=batch_size, shuffle=False),
                    total=int(len(inputs) / batch_size)):
                # get predictions
                nb_inputs = len(input_batch)  # usually batch size, but could be lower
                seq_len = len(input_batch[0])
                prediction = self.predictions_fn(input_batch, mask_batch)
                prediction = np.reshape(prediction, (nb_inputs, -1))
                prediction = list(prediction)
                predictions = predictions + prediction

                # get error and accuracy
                error, accuracy = self.validate_fn(input_batch, mask_batch, target_batch)
                # import pdb;pdb.set_trace()
                totError += error
                totAcc += accuracy
                n_batches += 1

            avg_error = totError / n_batches * 100
            avg_Acc = totAcc / n_batches * 100

            logger_evaluate.info(" Accuracy: %s", avg_Acc)
            inputs = inputs_bak
            targets = targets_bak
            valid_frames = valid_frames_bak
            general_tools.saveToPkl(predictions_path, [inputs, predictions, targets, valid_frames, avg_Acc])

        else:
            # TODO make sure this works when you don't give targets and valid_frames
            for inputs, masks, seq_lengths in tqdm(
                    iterate_minibatches_noTargets(inputs, batch_size=batch_size, shuffle=False),
                    total=len(inputs)):
                # get predictions
                nb_inputs = len(inputs)  # usually batch size, but could be lower
                seq_len = len(inputs[0])
                prediction = self.predictions_fn(inputs, masks)
                prediction = np.reshape(prediction, (nb_inputs, -1))
                prediction = list(prediction)
                predictions = predictions + prediction

            inputs = inputs_bak
            general_tools.saveToPkl(predictions_path, [inputs, predictions])
        logger_evaluate.info("* Done")
        end_evaluation_time = time.time()
        eval_duration = end_evaluation_time - program_start_time
        logger_evaluate.info('Total time: {:.3f}'.format(eval_duration))
        # Print the results
        try:
            printEvaluation(wav_filenames, inputs, predictions, targets, valid_frames, avg_Acc, range(len(inputs)),
                            logger=logger_evaluate, only_final_accuracy=True)
        except:
            pdb.set_trace()
        logger_evaluate.info('Evaluation duration: {:.3f}'.format(eval_duration))
        logger_evaluate.info('Printing duration: {:.3f}'.format(time.time() - end_evaluation_time))

        # close the log handler
        fh.close()
        logger_evaluate.removeHandler(fh)


evaluator = modelEvaluator()
