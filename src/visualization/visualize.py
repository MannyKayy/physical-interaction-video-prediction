import sys
import os
import glob
import csv
import click
import logging
import math

import numpy as np
import matplotlib.pyplot as plt

import chainer
import chainer.functions as F

from PIL import Image

# Put the main path in the systems path
sys.path.append("/".join(sys.path[0].split("/")[:-2]))

from src.models.train_model import Model
from src.models.train_model import concat_examples
from src.models.predict_model import get_data_info

# ========================
# Helpers functions (hlpr)
# ========================

def get_coordinates(data, std=[]):
    """
        Extract the coordinate used for plotting for a network

        Args:
            data (float[]): 1D array containing the data to plot
            std (float[]): 1D array to create the "box" arround the curve
        Returns:
            (float[]), (float[]), (float[])
    """
    coord = []
    box = []
    y_min = np.min(data, axis=0)
    y_max = np.max(data, axis=0)

    # Scale the data between range [-1.0, 1.0]
    #data = scale_data(data, mins=y_min, maxs=y_max)

    for i in xrange(len(data)):
        # Create the "box" around the curve
        if len(std) == len(data):
            box.append([data[i] - 1.0 * std[i], data[i] + 1.0 * std[i]])

        coord.append([i, data[i]])

    return np.array(coord, dtype=np.float32), np.array(box, dtype=np.float32), [0, len(coord), y_min, y_max]

def scale_data(data, high=1.0, low=-1.0, maxs=None, mins=None):
    """
        Scale data between [low, high]

        Args:
            data (float[]): 1D array of values to scale
            high (float): upperbound of the scale
            low (float): lowerbound of the scale
            maxs (float): max value in data
            mins (float): min value in data
        Returns:
            (float[])
    """
    if mins is None:
        mins = np.min(data, axis=0)
    if maxs is None:
        maxs = np.max(data, axis=0)
    rng = maxs - mins
    return high - (((high - low) * (maxs - data)) / rng)

def plot_data(coordinate, box=[], plt_inst=None, **kwargs):
    """
        Plot the coordinate with the "std box" around the curve

        Args:
            coordinate (float[]): 1D array of the coordinate to plot
            box (float[]): 1D array of the box around the curve
            plt_inst (pyplot): pyplot instance
        Returns:
            (plt_inst)
    """
    if plt_inst is None:
        plt_inst = plt
    
    if len(box) == len(coordinate):
        plt_inst.fill_between(np.arange(len(box)), box[:, 0:1].squeeze(), box[:, 1:].squeeze(), zorder=1, alpha=0.2)

    plt_inst.plot(coordinate[:, 0:1].squeeze(), coordinate[:, 1:].squeeze(), **kwargs)

    return plt_inst

def plot_losses_curves(train_network, valid_network, x_label="Epoch", y_label="Loss", title="Network loss"):
    """
        Plot multiple curves on the same graph

        Args:
            train_network (float[]): the train loss
            valid_network (float[]): the valid loss
            x_label (string): label of x axis
            y_label (string): label of y axis
            title (string): title of the graph
        Returns:
            (plt)
    """
    # Extract the coordinate of the losses
    coord_network_train, box_network_train, stats_network_train = [], [], []
    coord_network_valid, box_network_valid, stats_network_valid = [], [], []
    if len(train_network) > 0:
        coord_network_train, box_network_train, stats_network_train = get_coordinates(train_network[:, 0], train_network[:, 1])
    if len(valid_network) > 0:
        coord_network_valid, box_network_valid, stats_network_valid = get_coordinates(valid_network[:, 0], valid_network[:, 1])

    plt.figure(1)
    plt.subplot("{0}{1}{2}".format(1, 1, 1))
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(title + " (iteration #{})".format(len(coord_network_train) if len(coord_network_train) > 0 else len(coord_network_valid)))
    plt.ylim(
        min(stats_network_train[2] if len(stats_network_train) > 0 else 0, stats_network_valid[2] if len(stats_network_valid) > 0 else 0),
        max(stats_network_train[3] if len(stats_network_train) > 0 else 0, stats_network_valid[3] if len(stats_network_valid) > 0 else 0)
    )

    if len(coord_network_train) > 0:
        plot_data(coord_network_train, box_network_train, plt, label="Train")
    if len(coord_network_valid) > 0:
        plot_data(coord_network_valid, box_network_valid, plt, label="Test")

    plt.legend(ncol=2 if len(coord_network_train) > 0 and len(coord_network_valid) > 0 else 1, loc="upper right", fontsize=10)

    return plt 

def plot(ctx, xaxis, yaxis, title, cb):
    plt.cla()
    plt.xlabel(xaxis)
    plt.ylabel(yaxis)
    plt.title(title)
    xcoord = []
    ycoord = []
    for i in xrange(len(ctx)):
        points = cb(ctx[i], i)
        if len(points) != 0:
            xcoord.append(points[0])
            ycoord.append(points[1])

    plt.plot(xcoord, ycoord)
    return plt

def visualize_layer_activation(model, x, layer_idx):
    logger = logging.getLogger(__name__)

    activations = model.activations(layer_idx, x, 0)

    # Rescale the activation [0, 255]
    activations -= activations.min()
    activations /= activations.max()
    activations *= 255
    activations = activations.astype(np.uint8)

    # Plot the bitmap of the masks
    filters = activations.shape[1]
    plt.figure(1, figsize=(activations.shape[3]*filters,activations.shape[2]*filters))
    n_column = math.floor(math.sqrt(filters))
    n_row = math.ceil(filters / n_column) + 1
    for i in xrange(filters):
        plt.subplot(n_row, n_column, i+1)
        plt.title("Filter:" + str(i))
        plt.imshow(activations[0,i,:,:], interpolation="nearest", cmap="gray")

    return plt
    #images = []
    #for i, activation in enumerate(activations):
    #    print(activation[0])
    #    exit()
    #    #file_name = visualization_path + "/" + model + "-feature-map-{0}-{1}-iteration-{2}".format(layer_idx, i, iteration_number) + ".png"
    #    image = np.rollaxis(activation, 0, 3) # c, h, w => h, w, c
    #    print(image)
    #    exit()
    #    image = Image.fromarray(image)
    #    images.append(image)
    #    #image.save(file_name)
    #return images


@click.command()
@click.argument('model', type=click.STRING)
@click.option('--layer_idx', type=click.INT, default=0, help='Convolution layer index.')
@click.option('--model_name', type=click.STRING, default=None, help='Name of the model to visualize.')
@click.option('--data_index', type=click.INT, default=None, help='Index of the data for the visualization.')
@click.option('--model_dir', type=click.Path(exists=True), default='models', help='Directory containing data.')
@click.option('--output_dir', type=click.Path(), default='reports', help='Directory for model checkpoints.')
@click.option('--data_dir', type=click.Path(exists=True), default='data/processed/brain-robotics-data/push/push_testnovel', help='Directory containing data.')
@click.option('--time_step', type=click.INT, default=8, help='Number of time steps to predict.')
@click.option('--model_type', type=click.STRING, default='', help='Type of the trained model.')
@click.option('--schedsamp_k', type=click.FLOAT, default=900.0, help='The k parameter for schedules sampling. -1 for no scheduled sampling.')
@click.option('--context_frames', type=click.INT, default=2, help='Number of frames before predictions.')
@click.option('--use_state', type=click.INT, default=1, help='Whether or not to give the state+action to the model.')
@click.option('--num_masks', type=click.INT, default=10, help='Number of masks, usually 1 for DNA, 10 for CDNA, STP.')
@click.option('--image_height', type=click.INT, default=64, help='Height of one predicted frame.')
@click.option('--image_width', type=click.INT, default=64, help='Width of one predicted frame.')
def main(model, layer_idx, model_name, data_index, model_dir, output_dir, data_dir, time_step, model_type, schedsamp_k, context_frames, use_state, num_masks, image_height, image_width):
    logger = logging.getLogger(__name__)

    model_path = model_dir + '/' + model
    visualization_path = output_dir + '/' + model
    if not os.path.exists(model_path):
        raise ValueError("Directory {} does not exists".format(model_path))

    if not os.path.exists(visualization_path):
        os.makedirs(visualization_path)

    # @TODO Need to be dynamic reporting
    training_global_losses = None
    if os.path.exists(model_path + '/training-global_losses.npy'): training_global_losses = np.load(model_path + '/training-global_losses.npy')

    training_global_losses_valid = None
    if os.path.exists(model_path + '/training-global_losses_valid.npy'):
        training_global_losses_valid = np.load(model_path + '/training-global_losses_valid.npy')

    #graph = plot(training_global_losses, 'Epoch', 'Mean', 'Training global losses', lambda pos, i: [i, pos[0]] if pos[0] != 0 else [] )
    #graph.savefig(visualization_path + '/training_global_losses')
    #graph = plot(training_global_losses, 'Epoch', 'Mean', 'Training global losses valid', lambda pos, i: [i, pos[0]] if pos[0] != 0 else [] )
    #graph.savefig(visualization_path + '/training_global_losses_valid')

    # @TODO: fix the training loss
    #plt_inst = plot_losses_curves(training_global_losses if training_global_losses is not None else [], training_global_losses_valid if training_global_losses_valid is not None else [])
    logger.info("Plotting the loss curves")
    plt_inst = plot_losses_curves(training_global_losses if training_global_losses is not None else [], [])
    iteration_number = len(training_global_losses) if len(training_global_losses) > 0 else len(training_global_losses_valid)
    plt_inst.savefig(visualization_path + "/" + model + "-iteration-{}".format(iteration_number) + ".png")
    plt_inst = plot(training_global_losses, 'Epoch', 'Mean', 'Training global losses valid', lambda pos, i: [i, pos[0]] if pos[0] != 0 else [] )
    plt_inst.savefig(visualization_path + "/" + model + "-validation-iteration-{}".format(iteration_number) + ".png")

    # Plot the masks activation
    if model_name is not None:
        if not os.path.exists(model_path + '/' + model_name):
            raise ValueError("Model name {} does not exists".format(model_name))

        logger.info("Loading data {}".format(data_index))
        image, image_pred, image_bitmap_pred, action, state = get_data_info(data_dir, data_index)
        img_pred, act_pred, sta_pred = concat_examples([[image_pred, action, state]])

        # Extract the information about the model
        if model_type == '':
            split_name = model.split("-")
            if len(split_name) != 4:
                raise ValueError("Model {} is not recognized, use --model_type to describe the type".format(model))
            model_type = split_name[2]

        # Load the model for prediction
        logger.info("Importing model {0}/{1} of type {2}".format(model_dir, model, model_type))
        model = Model(
            num_masks=num_masks,
            is_cdna=model_type == 'CDNA',
            is_dna=model_type == 'DNA',
            is_stp=model_type == 'STP',
            use_state=use_state,
            scheduled_sampling_k=schedsamp_k,
            num_frame_before_prediction=context_frames,
            prefix='predict'
        )

        chainer.serializers.load_npz(model_path + '/' + model_name, model)
        logger.info("Model imported successfully")
        
        logger.info("Predicting input for the activation map")
        resize_img_pred = []
        for i in xrange(len(img_pred)):
            resize = F.resize_images(img_pred[i], (image_height, image_width))
            resize = F.cast(resize, np.float32) / 255.0
            resize_img_pred.append(resize.data)
        resize_img_pred = np.asarray(resize_img_pred, dtype=np.float32)
        plt_inst = visualize_layer_activation(model, [resize_img_pred, act_pred, sta_pred], layer_idx)
        plt_inst.show()



if __name__ == '__main__':
    log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    #logging.basicConfig(level=logging.INFO, format=log_fmt, stream=sys.stdout)
    logging.basicConfig(level=logging.INFO, format=log_fmt)

    main()
