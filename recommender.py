from __future__ import division
from __future__ import print_function

import argparse
import numpy as np
import tensorflow as tf

from cell import RecommenderCell
from reader import Dataset
from embeddings import Embeddings

class RecommenderRNN(object):
    
    def __init__(self, num_users, num_items, max_seq_len, is_training, hidden_size=64,
                 batch_size=1, learning_rate=0.1, inp_D=64):
        
	self._batch_size = batch_size
	self._hidden_unit_size = hidden_size
	# sort inputs for user_lstm and item_lstm
        # Placeholders for input data
	self._inputs = tf.placeholder(dtype=tf.float32, shape=[batch_size, 2, max_seq_len, 3], name="inputs")
	self._targets = tf.placeholder(dtype=tf.float32, shape=[batch_size, max_seq_len], name="targets")
        self._seq_lengths = tf.placeholder(tf.int32, shape=[batch_size], name="seq_lengths")
	self._u_emb = tf.placeholder(dtype=tf.float32, shape=[num_users, inp_D-1], name="u_emb")
	self._i_emb = tf.placeholder(dtype=tf.float32, shape=[num_items, inp_D-1], name="i_emb")

	# Variables for embedding sequences
	u_emb_seq = tf.concat(
		[tf.nn.embedding_lookup(self._u_emb, self._inputs[:,0,:,0]),self._inputs[:,0,:,2]], 3)
	i_emb_seq = tf.concat(
		[tf.nn.embedding_lookup(self._i_emb, self._inputs[:,1,:,0]),self._inputs[:,1,:,2]], 3)

	print("u_emb_seq shape: ",u_emb_seq.shape)

	inputs = tf.squeeze(tf.concat([u_emb_seq, i_emb_seq], 3))
	print("inputs: ", inputs)
        
        # Recommender LSTM cell
        cell = RecommenderCell(hidden_size, batch_size, inp_D)
        self._initial_state = cell.zero_state(batch_size, tf.float32)
        
        # Will try mini-batching in next version
  
	outputs, final_state = tf.nn.dynamic_rnn(cell, inputs, sequence_length=self.seq_lengths, 
                               initial_state=self._initial_state)
	#shape(hid_state): [batch_size x seq_len x hidden_size]

	_out_u, _out_i = tf.split(value=outputs, num_or_size_splits=2, axis=2)
	_out_u = tf.reshape(_out_u, [batch_size, max_seq_len, hidden_size, 1])
	_out_i = tf.reshape(_out_i, [batch_size, max_seq_len, hidden_size, 1])
        _outputs = tf.squeeze(tf.matmul(_out_u, _out_i, transpose_a=True, name="_outputs"))

	# Back-propagating errors only for the last time step
	# outputs[:len(outputs)-2] = 0
	# _outputs = tf.zeros(tf.shape(outputs))
	# _outputs[len(_outputs)-1] = outputs[len(outputs)-1] 

	# Calculating loss
	self.loss = tf.losses.mean_squared_error(_outputs, self.targets)

	if not is_training:
	    self._train_op = tf.no_op()
	    return

	# Optimization for training
	optimizer = tf.train.AdamOptimizer(learning_rate)
	self._train_op = optimizer.minimize(self.loss)

	# Initializing embedding variables
	#self._embeddings_reset = list()
	#op = user_emb.assign()
	#self._optimizer_reset.append(op)

    # Need to define necessary properties
    @property
    def inputs(self):
	return self._inputs

    @property
    def targets(self):
	return self._targets

    @property
    def seq_lengths(self):
	return self._seq_lengths

    @property
    def initial_state(self):
	return self._initial_state

    @property
    def batch_size(self):
	return self._batch_size

    @property
    def hidden_unit_size(self):
	return self._hidden_unit_size

    @property
    def u_emb(self):
	return self._u_emb

    @property
    def i_emb(self):
	return self._i_emb

def run_batch(sess, model, iterator, init_state):
    """
    """
    #costs = np.zeros
    inputs, targets, seq_lens = iterator
    # shape(inputs): [seq_len x D x 2]
    # shape(targets): [seq_len]
    # where D = shape[embedding,ts] or D = shape[embedding,1/0,ts]
    print("inputs:",inputs)
    print("targets:",targets)
    fetches = [model.loss, model.final_state, model.train_op]
    feed_dict = {}
    feed_dict[model.inputs] = inputs
    feed_dict[model.targets] = targets
    feed_dict[model.seq_lengths] = seq_lens
    feed_dict[model.initial_state] = init_state
    errors, state, _ = sess.run(fetches, feed_dict)
    
    return errors, state


def run_epoch(sess, train_model, valid_model, train_iter, valid_iter):
    """
    """
    train_errors = list()
    valid_errors = list()
    # Training model on train data
    for train in train_iter:
	state = sess.run(train_model.initial_state)
	errors, state = run_batch(sess, train_model, train, state)
	train_errors.extend(errors)
    # Validating on probe data
    for valid in valid_iter:
        state = sess.run(train_model.initial_state)
	errors, state = run_batch(sess, valid_model, valid, state)
	valid_errors.extend(errors)

    return (np.nansum(train_errors), np.nansum(valid_errors))

def main(args):
    """
    """

    train_data = Dataset.from_path(args.train_path, args.batch_size,
        args.hidden_size-1, mode="train")
    valid_data = Dataset.from_path(args.valid_path, args.batch_size,
        args.hidden_size-1, mode="valid")
    num_users = train_data.num_users
    num_items = train_data.num_items
#    print("Doing batch preprocessing for training data...")
#    train_data.batch_preprocessing(u_emb, i_emb)
#    print("Doing batch preprocessing for validation data...")
#    valid_data.batch_preprocessing(u_emb, i_emb)
#    del u_emb
#    del i_emb
    print("Preparing batches for training data...")
    train_data.prepare_batches()
    print("Preparing batches for validation data...")
    valid_data.prepare_batches()

    emb_settings = {
	"emb_size": args.input_emb_size-1,
	"num_samples": 100,
	"batch_size": 10,
	"learning_rate": 0.1,
	"epoch": 20,
    }

    settings = {
        "inp_D": args.input_emb_size,
        "hidden_size": args.hidden_size,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
    }

    with tf.Graph().as_default(), tf.Session() as sess:

        with tf.variable_scope("User_Embeddings"):
	    u_emb_model = Embeddings(num_classes=num_users, **emb_settings)
        with tf.variable_scope("Item_Embeddings"):
	    i_emb_model = Embeddings(num_classes=num_items, **emb_settings)
        with tf.variable_scope("model"):
            train_model = RecommenderRNN(num_users, num_items, train_data.max_seq_len,
                 is_training=True, **settings)
        with tf.variable_scope("model", reuse=True):
            valid_model = RecommenderRNN(num_users, num_items, valid_data.max_seq_len,
                is_training=False, **settings)

	tf.global_variables_initializer().run()
        # Create embeddings for user and item sequences and prepare batches
        print("Creating embeddings for users...")
        u_emb_model.create_embeddings(sess)
	u_emb = u_emb_model.embeddings
        print("Creating embeddings for items...")
        i_emb_model.create_embeddings(sess)
	i_emb = i_emb_model.embeddings 

	feed_dict={}
	feed_dict[train_model.u_emb] = u_emb
	feed_dict[train_model.i_emb] = i_emb
	feed_dict[valid_model.u_emb] = u_emb
	feed_dict[valid_model.i_emb] = i_emb
	sess.run(feed_dict)
	# free some space
	del u_emb_model
	del i_emb_model
	assert u_emb_model == None

	for i in range(1, args.num_epochs+1):
	    # Train on random batches of data
	    train_iter = train_data.iter_batches()
	    valid_iter = valid_data.iter_batches()

	    train_error, valid_error = run_epoch(sess, train_model, valid_model,
			train_iter, valid_iter)

	    print("[Epoch {}] Train RMSE: {:.3f}".format(i, train_error))
	    print("[Epoch {}] Valid RMSE: {:.3f}".format(i, valid_error))


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("train_path", help="path to training data")
    parser.add_argument("valid_path", help="path to validation data")
    parser.add_argument("--batch-size", type=int, default=10,
	help="number of sequences processed in parallel")
    parser.add_argument("--input-emb-size", type=int, default=64,
	help="dimension of input features")
    parser.add_argument("--hidden-size", type=int, default=64,
	help="number of hidden units in the RNN cell")
    parser.add_argument("--learning-rate", type=float, default=0.01,
	help="model learning rate")
    parser.add_argument("--num-epochs", type=int, default=10,
	help="number of epochs to learn")
    parser.add_argument("--verbose", action="store_true", default=False,
	help="enable display of debugging messages")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
#    if args.verbose:
    main(args)

