######################################################################################
#   FileName:       [ trainLSTM.py ]                                                 #
#   PackageName:    [ LSTM_berkeley ]                                                #
#   Synopsis:       [ Train LSTM (Berkeley) framework for visual question answering ]#
#   Author:         [ MedusaLafayetteDecorusSchiesse]                                #
######################################################################################

import numpy as np
import scipy.io as sio
from sklearn.metrics.pairwise import cosine_similarity
import sys
import argparse
import joblib
import time
import signal
import random
from progressbar import Bar, ETA, Percentage, ProgressBar

from keras.models import Sequential
from keras.layers.core import Dense, Activation
from keras.layers.recurrent import LSTM
from keras.utils import generic_utils

from utils import  LoadIds, LoadQuestions, LoadAnswers, LoadChoices, LoadGloVe ,LoadInceptionFeatures ,GetQuestionsTensor,GetImgQuestionsTensor ,GetAnswersMatrix, GetChoicesTensor, MakeBatches, InterruptHandler

def main():
    start_time = time.time()
    signal.signal(signal.SIGINT, InterruptHandler)
    #signal.signal(signal.SIGKILL, InterruptHandler)
    signal.signal(signal.SIGTERM, InterruptHandler)

    parser = argparse.ArgumentParser(prog='trainLSTM.py',
            description='Train LSTM model for visual question answering')
    parser.add_argument('--lstm-hidden-units', type=int, default=512, metavar='<lstm-hidden-units>')
    parser.add_argument('--lstm-hidden-layers', type=int, default=1, metavar='<lstm-hidden-layers>')
    #parser.add_argument('--dropout', type=float, default=0.5, metavar='<dropout-rate>')
    parser.add_argument('--num-epochs', type=int, default=100, metavar='<num-epochs>')
    #parser.add_argument('--model-save-interval', type=int, default=5, metavar='<interval>')
    parser.add_argument('--batch-size', type=int, default=128, metavar='<batch-size>')
    args = parser.parse_args()

    Inc_features_dim = 2048
    word_vec_dim = 300
    max_len = 30
    data_dir = '/home/mlds/data/0.2_val/'
    ######################
    #      Load Data     #
    ######################

    print('Loading data...')

    train_id_pairs, train_image_ids = LoadIds('train', data_dir)
    dev_id_pairs, dev_image_ids = LoadIds('dev', data_dir)

    train_questions = LoadQuestions('train', data_dir)
    dev_questions = LoadQuestions('dev', data_dir)

    train_choices = LoadChoices('train', data_dir)
    dev_choices = LoadChoices('dev', data_dir)

    train_answers = LoadAnswers('train', data_dir)
    dev_answers = LoadAnswers('dev', data_dir)

    print('Finished loading data.')
    print('Time: %f s' % (time.time()-start_time))

    print('-'*100, file=sys.stderr)
    print('Training Information', file=sys.stderr)
    print('# of LSTM hidden units: %i' % args.lstm_hidden_units, file=sys.stderr)
    print('# of LSTM hidden layers: %i' % args.lstm_hidden_layers, file=sys.stderr)
    #print('Dropout: %f' % args.dropout, file=sys.stderr)
    print('# of training epochs: %i' % args.num_epochs, file=sys.stderr)
    print('Batch size: %i' % args.batch_size, file=sys.stderr)
    print('# of train questions: %i' % len(train_questions), file=sys.stderr)
    print('# of dev questions: %i' % len(dev_questions), file=sys.stderr)
    print('-'*100, file=sys.stderr)

    ######################
    # Model Descriptions #
    ######################

    # LSTM model
    model = Sequential()
    model.add(LSTM(
        output_dim=args.lstm_hidden_units, return_sequences=True, input_shape=(max_len, Inc_features_dim + word_vec_dim)
        ))
    for i in range(args.lstm_hidden_layers-2):
        model.add(LSTM(
            output_dim=args.lstm_hidden_units, return_sequences=True
            ))
    model.add(LSTM(output_dim=word_vec_dim, return_sequences=False))
    model.add(Activation('softmax'))

    json_string = model.to_json()
    model_filename = 'models/lstm_units_%i_layers_%i' % (args.lstm_hidden_units, args.lstm_hidden_layers)
    open(model_filename + '.json', 'w').write(json_string)

    # loss and optimizer
    model.compile(loss='categorical_crossentropy', optimizer='rmsprop')
    print('Compilation finished.')
    print('Time: %f s' % (time.time()-start_time))

    ##############################################
    #  Load Word Vectors and Inception Features  #
    ##############################################

    # load GloVe vectors
    print('Loading GloVe vectors...')
    word_embedding, word_map = LoadGloVe()
    print('GloVe vectors loaded')
    print('Time: %f s' % (time.time()-start_time))

    print('Loading Inception features...')
    Inc_features, img_map = LoadInceptionFeatures()
    print('Inception features loaded')
    print('Time: %f s' % (time.time()-start_time))

    ######################
    #    Make Batches    #
    ######################

    print('Making batches...')

    # training batches
    train_question_batches = [ b for b in MakeBatches(train_questions, args.batch_size, fillvalue=train_questions[-1]) ]
    train_answer_batches = [ b for b in MakeBatches(train_answers['toks'], args.batch_size, fillvalue=train_answers['toks'][-1]) ]
    train_image_batches = [b for b in MakeBatches(train_image_ids, args.batch_size, fillvalue=train_image_ids[-1])]
    train_indices = list(range(len(train_question_batches)))

    # validation batches
    dev_question_batches = [ b for b in MakeBatches(dev_questions, args.batch_size, fillvalue=dev_questions[-1]) ]
    dev_answer_batches = [ b for b in MakeBatches(dev_answers['labs'], args.batch_size, fillvalue=dev_answers['labs'][-1]) ]
    dev_image_batches = [b for b in MakeBatches(dev_image_ids, args.batch_size, fillvalue=dev_image_ids[-1])]
    dev_choice_batches = [ b for b in MakeBatches(dev_choices, args.batch_size, fillvalue=dev_choices[-1]) ]

    print('Finished making batches.')
    print('Time: %f s' % (time.time()-start_time))


    ######################
    #      Training      #
    ######################

    dev_accs = []
    max_acc = -1
    max_acc_epoch = -1

    print('Training started...')
    for k in range(args.num_epochs):
        print('Epoch %i' % (k+1), file=sys.stderr)
        print('-'*80)
        print('Epoch %i' % (k+1))
        progbar = generic_utils.Progbar(len(train_indices)*args.batch_size)
        # shuffle batch indices
        random.shuffle(train_indices)
        for i in train_indices:
            X_imgquestion_batch = GetImgQuestionsTensor(train_image_batches[i], Inc_features, img_map, train_question_batches[i], word_embedding, word_map)
            Y_answer_batch = GetAnswersMatrix(train_answer_batches[i], word_embedding, word_map)
            loss = model.train_on_batch(X_imgquestion_batch, Y_answer_batch)
            loss = loss[0].tolist()
            progbar.add(args.batch_size, values=[('train loss', loss)])

        #if k % args.model_save_interval == 0:
            #model.save_weights(model_filename + '_epoch_{:03d}.hdf5'.format(k+1), overwrite=True)

        # evaluate on dev set
        progbar = generic_utils.Progbar(len(dev_question_batches)*args.batch_size)

        dev_correct = 0

        for i in range(len(dev_question_batches)):
            # feed forward
            X_imgquestion_batch = GetImgQuestionsTensor(dev_image_batches[i], Inc_features, img_map, dev_question_batches[i], word_embedding, word_map)
            prob = model.predict_proba(X_imgquestion_batch, args.batch_size, verbose=0)

            # get word vecs of choices
            choice_feats = GetChoicesTensor(dev_choice_batches[i], word_embedding, word_map)
            similarity = np.zeros((5, args.batch_size), float)
            # calculate cosine distances
            for j in range(5):
                similarity[j] = np.diag(cosine_similarity(prob, choice_feats[j]))
            # take argmax of cosine distances
            pred = np.argmax(similarity, axis=0) + 1

            dev_correct += np.count_nonzero(dev_answer_batches[i]==pred)
            progbar.add(args.batch_size)

        dev_acc = float(dev_correct)/len(dev_questions)
        dev_accs.append(dev_acc)
        print('Validation Accuracy: %f' % dev_acc)
        print('Validation Accuracy: %f' % dev_acc, file=sys.stderr)
        print('Time: %f s' % (time.time()-start_time))
        print('Time: %f s' % (time.time()-start_time), file=sys.stderr)

        if dev_acc > max_acc:
            max_acc = dev_acc
            max_acc_epoch = k
            model.save_weights(model_filename + '_best.hdf5', overwrite=True)

    #model.save_weights(model_filename + '_epoch_{:03d}.hdf5'.format(k+1))
    print(dev_accs, file=sys.stderr)
    print('Best validation accuracy: epoch#%i' % max_acc_epoch)
    print('Training finished.')
    print('Training finished.', file=sys.stderr)
    print('Time: %f s' % (time.time()-start_time))
    print('Time: %f s' % (time.time()-start_time), file=sys.stderr)

if __name__ == "__main__":
    main()
