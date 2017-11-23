import argparse
import tensorflow as tf
from model import model
from reader import *
from ultize import *
import numpy as np
from collections import Counter
import model.model_add_aligned as model_add_aligned
import time
import logging
parser = argparse.ArgumentParser(description='parameters.')
parser.add_argument('--batch_size',type= int ,default = 20,
                    help='the origin data path')
parser.add_argument('--num_units', type= int, default = 200,
                    help='the path of processed data ')
parser.add_argument('--is_training', type= bool, default = True,
                    help='Ture means inference')
parser.add_argument('--restore_path', type= str, default = "../modelRestor/word-level/",
                    help='the path of retore path ')
parser.add_argument('--src_vocab_size', type= int, default = 17689,
                    help='the size of vocab size ')
parser.add_argument('--vocab_path', type= str, default = None,
                    help='the size of vocab size ')
parser.add_argument('--input_embedding_size', type= int, default = 200,
                    help='the size of embedding size ')
parser.add_argument('--data_path', type= str, default = "../input/data",
                    help='the path of data')
parser.add_argument('--vector_path', type= str, default = "../cha_vectors.bin",
                    help='the path of vector and vocab')
parser.add_argument('--result_path', type= str, default = "../output/result",
                    help='the path of result')
parser.add_argument('--test', type= str, default = "inference",
                    help='whether to check run ok')
parser.add_argument('--num_layer', type= int, default =3,
                    help='layers in biRNN')
parser.add_argument('--epoch', type= int, default =10,
                    help='the training epochs')
parser.add_argument('--pos_vocab_path', type= str, default ="pos_vocab",
                    help='the pos vocab')
parser.add_argument('--pos_vocab_size', type= int, default = 30,
                    help='the pos vocab size')


args = parser.parse_args()

# Read cha_vectors.bin
if args.vocab_path  is not None:
    vocab = loadvocab(args.vocab_path)
    vocab_size = len(vocab)
    embedding_dim = args.input_embedding_size 
    print("load vocab")
else:    
    vocab,embd = loadWord2Vec(args.vector_path)
    vocab_size = len(vocab)
    embedding_dim = len(embd[0])  
    print("load vector")  

vocab_index = range(vocab_size)
vocab = dict(zip(vocab,vocab_index)) # vocab
id_vocab = {v:k for k, v in vocab.items() }

# Define reader
reader  = Reader(args,vocab)
args.src_vocab_size = vocab_size
args.input_embedding_size = embedding_dim
args.pos_vocab_size =  len(reader.pos_vocab)  # size of vocab


trainModel = model_add_aligned.model(args)
trainModel.build_model()

# para_config = tf.ConfigProto(
#                 inter_op_parallelism_threads = 2,
#                 intra_op_parallelism_threads = 10)

sess = tf.Session()#config=para_config)
saver = tf.train.Saver()
ckpt_state = tf.train.get_checkpoint_state(args.restore_path)


graph=  tf.get_default_graph()
writer = tf.summary.FileWriter(args.restore_path,graph=graph)


if ckpt_state == None:
    print("Cant't load model,starting initial")
    sess.run(tf.global_variables_initializer())
else:
    try:
        saver.restore(sess, ckpt_state.model_checkpoint_path)
        print("restor model successed")
    except:
        print("loading error.")

# start to inference
print("model path:".format(args.restore_path))
reader.reset()
for m_epoch in range(args.epoch):

    per_loss_start = 0
    
    per_loss_end = 0
    
    for step in  range(reader.num_examples // args.batch_size):

        query_ls , passage_ls, answer_ls, answer_p_s, answer_p_e,query_pos_ls,passage_pos_ls = reader.get_batch()
        
        feed = get_dict(trainModel,query_ls , passage_ls, answer_ls, answer_p_s, answer_p_e, query_pos_ls,passage_pos_ls)
        
        toSee = [trainModel.cross_entropy_start,trainModel.cross_entropy_end,trainModel.summary_op,trainModel.start_train_op,trainModel.end_train_op]
        
        loss_start,loss_end, summary_re, _, _ = sess.run(toSee,feed_dict=feed)
        
        per_loss_start  += loss_start
        
        per_loss_end    += loss_end
        
        # save summary
        if step % 100 ==0:
            print("iterator: {} ，loss_start is :{} , loss_end is:{}".format(reader.question_index, per_loss_start /100,per_loss_end/100 ))
            writer.add_summary(summary_re,global_step = trainModel.global_step.eval(session = sess))
            per_loss_start = 0
            per_loss_end = 0
            # inference
            pre_s ,pre_e =sess.run([trainModel.p_W_q,trainModel.p_We_q],feed_dict=feed)
            s_p = np.argmax(pre_s[0])
            e_p = np.argmax(pre_e[0])
            if  s_p <= e_p:
                print("question:{},passage:{},answer:{},pre:{},start:{},end:{},sequence_len:{}".format(
                    id2word(query_ls[0],id_vocab),
                    id2word(passage_ls[0],id_vocab),
                    id2word(answer_ls[0],id_vocab),
                    id2word(passage_ls[0][s_p:e_p],id_vocab),
                    s_p,
                    e_p,
                    len(passage_ls[0])))
                #print("start_martix:{},end_martix:{}".format(pre_s[0],pre_e[0]))
        if step%1000 == 0:
            saver.save(sess,args.restore_path,global_step = trainModel.global_step.eval(session = sess))
    reader.reset()

print("finished")