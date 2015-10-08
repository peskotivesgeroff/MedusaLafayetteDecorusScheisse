#########################################################
#   FileName:	    [ model.py ]			#
#   PackageName:    []					#
#   Sypnosis:	    [ Define DNN model ]		#
#   Author:	    [ MedusaLafayetteDecorusSchiesse]   #
#########################################################

import numpy as np
import theano
import theano.tensor as T
import macros

########################
# function definitions #
########################

# activation functions
def ReLU(x):
    return T.switch(x < 0, 0, x)

def SoftMax(vec):
    vec = T.exp(vec)
    return vec / vec.sum()

# utility functions 
def Update(params, gradients):
    param_updates = [ (p, p - macros.LEARNING_RATE * g) for p, g in zip(params, gradients) ]
    return param_updates

###############################
# initialize shared variables #
###############################

# inputs
x = T.matrix(dtype=theano.config.floatX)
y_hat = T.matrix(dtype=theano.config.floatX)

# parameters
W1 = theano.shared(np.random.randn(macros.NEURONS_PER_LAYER, macros.INPUT_DIM).astype(dtype=theano.config.floatX)/np.sqrt(macros.INPUT_DIM))
b1 = theano.shared(np.random.randn(macros.NEURONS_PER_LAYER).astype(dtype=theano.config.floatX))
W = theano.shared(np.random.randn(macros.OUTPUT_DIM, macros.NEURONS_PER_LAYER).astype(dtype=theano.config.floatX)/np.sqrt(macros.INPUT_DIM))
b = theano.shared(np.random.randn(macros.OUTPUT_DIM).astype(dtype=theano.config.floatX))

params = [W1, b1, W, b]

#########
# model #
#########

# function (feedforward)
a1 = ReLU(T.dot(W1,x) + b1.dimshuffle(0, 'x'))
y = SoftMax( T.dot(W,a1) + b.dimshuffle(0, 'x') )

# cost function
cost = -T.log(T.dot(y.T, y_hat)).trace()/macros.BATCH_SIZE

# calculate gradient
dW1, db1, dW, db = T.grad(cost, [W1, b1, W, b])
dparams = [dW1, db1, dW, db]

####################
# output functions #
####################

# forward calculation
forward = theano.function(
        inputs=[x, y_hat],
        outputs=[y, cost],
		updates=Update(params, dparams)
        )
