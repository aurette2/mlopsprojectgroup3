
import os
import cv2
import keras
import random
import glob
import tensorflow as tf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import nibabel as nib
from dotenv import load_dotenv
import tensorflow.keras.backend as K
from keras.callbacks import CSVLogger
import tensorflow as tf
from tensorflow.keras.utils import plot_model
from tensorflow.keras.models import *
from tensorflow.keras.layers import *
from tensorflow.keras.optimizers import *
from tensorflow.keras.callbacks import ModelCheckpoint, ReduceLROnPlateau, EarlyStopping, TensorBoard

from project2.backend.app.metrics import dice_coef, precision, sensitivity, specificity, dice_coef_necrotic, dice_coef_edema, dice_coef_enhancing

load_dotenv()
# Get the base directory from the .env file
MODELS_DIR = os.getenv('MODELS_DIR')
TRAIN_DATASET_PATH = os.getenv('DATASET_BASE_PATH')

VOLUME_SLICES = 100
VOLUME_START_AT = 22 # first slice of volume that we will include
IMG_SIZE=128

class Unet:
    def __init__(self, img_size, num_classes, ker_init='he_normal', dropout=0.2, learning_rate=0.001):
        self.img_size = img_size
        self.num_classes = num_classes
        self.ker_init = ker_init
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.model = self.build_model()

    def build_model(self):
        inputs = Input((self.img_size, self.img_size, 2))
        conv1 = Conv2D(32, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(inputs)
        conv1 = Conv2D(32, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(conv1)

        pool = MaxPooling2D(pool_size=(2, 2))(conv1)
        conv = Conv2D(64, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(pool)
        conv = Conv2D(64, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(conv)

        pool1 = MaxPooling2D(pool_size=(2, 2))(conv)
        conv2 = Conv2D(128, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(pool1)
        conv2 = Conv2D(128, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(conv2)

        pool2 = MaxPooling2D(pool_size=(2, 2))(conv2)
        conv3 = Conv2D(256, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(pool2)
        conv3 = Conv2D(256, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(conv3)

        pool4 = MaxPooling2D(pool_size=(2, 2))(conv3)
        conv5 = Conv2D(512, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(pool4)
        conv5 = Conv2D(512, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(conv5)
        drop5 = Dropout(self.dropout)(conv5)

        up7 = Conv2D(256, 2, activation='relu', padding='same', kernel_initializer=self.ker_init)(UpSampling2D(size=(2, 2))(drop5))
        merge7 = concatenate([conv3, up7], axis=3)
        conv7 = Conv2D(256, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(merge7)
        conv7 = Conv2D(256, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(conv7)

        up8 = Conv2D(128, 2, activation='relu', padding='same', kernel_initializer=self.ker_init)(UpSampling2D(size=(2, 2))(conv7))
        merge8 = concatenate([conv2, up8], axis=3)
        conv8 = Conv2D(128, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(merge8)
        conv8 = Conv2D(128, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(conv8)

        up9 = Conv2D(64, 2, activation='relu', padding='same', kernel_initializer=self.ker_init)(UpSampling2D(size=(2, 2))(conv8))
        merge9 = concatenate([conv, up9], axis=3)
        conv9 = Conv2D(64, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(merge9)
        conv9 = Conv2D(64, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(conv9)

        up = Conv2D(32, 2, activation='relu', padding='same', kernel_initializer=self.ker_init)(UpSampling2D(size=(2, 2))(conv9))
        merge = concatenate([conv1, up], axis=3)
        conv = Conv2D(32, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(merge)
        conv = Conv2D(32, 3, activation='relu', padding='same', kernel_initializer=self.ker_init)(conv)

        conv10 = Conv2D(self.num_classes, (1, 1), activation='softmax')(conv)

        return Model(inputs=inputs, outputs=conv10)

    def compile_model(self, loss="categorical_crossentropy"):
        metrics = [
            'accuracy', 
            tf.keras.metrics.MeanIoU(num_classes=4), 
            dice_coef, 
            precision, 
            sensitivity, 
            specificity, 
            dice_coef_necrotic, 
            dice_coef_edema, 
            dice_coef_enhancing
        ]
        self.model.compile(loss=loss,
                           optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate),
                           metrics=metrics)

    def plot_model(self, file_path='unet_model.png'):
        plot_model(self.model, show_shapes=True, show_layer_names=True, to_file=file_path)

    def train(self, training_generator, validation_generator, epochs=35, train_ids=None):
        
        # Ensure the checkpoint directory exists
        if not os.path.exists(MODELS_DIR):
            os.makedirs(MODELS_DIR)

        callbacks = [
            ReduceLROnPlateau(monitor='val_loss', factor=0.2, patience=2, min_lr=0.000001, verbose=1),
            ModelCheckpoint(filepath=os.path.join(MODELS_DIR, 'model_.{epoch:02d}-{val_loss:.6f}.weights.h5'), verbose=1, save_best_only=True, save_weights_only=True),
            CSVLogger('training.log', separator=',', append=False)
        ]

        K.clear_session()
        history = self.model.fit(
            training_generator,
            epochs=epochs,
            steps_per_epoch=len(train_ids),
            callbacks=callbacks,
            validation_data=validation_generator
        )
        return history

    def save_model(self, file_path=os.path.join(MODELS_DIR,'my_model.keras')):
        self.model.save(file_path)

    def load_model(self, file_path=os.path.join(MODELS_DIR,'my_model.keras'), custom_objects=None):
        if custom_objects is None:
            custom_objects = {
                "accuracy": tf.keras.metrics.MeanIoU(num_classes=self.num_classes)
            }
        self.model = keras.models.load_model(file_path, custom_objects=custom_objects, compile=False)
        
    def compile_and_load_weights(self, weights_path):
        """A method to compile the model and load pre-trained weights.
            weights_path='/home/jupyter/model_.35-0.027031.weights.h5'
            weights_path=os.path.join(MODELS_DIR,'model_.35-0.027031.weights.h5')
            A method to load and preprocess an image.
        """
        
        self.model.compile(loss="categorical_crossentropy",
                           optimizer=tf.keras.optimizers.Adam(learning_rate=self.learning_rate),
                           metrics=['accuracy', tf.keras.metrics.MeanIoU(num_classes=4), dice_coef, precision, sensitivity, specificity, dice_coef_necrotic, dice_coef_edema, dice_coef_enhancing])
        self.model.load_weights(weights_path)
        print(f"Loaded weights from {weights_path}")
        
    # But it will be better to define it in DataGenerators ...
    def imageLoader(self, path):
        """Loads an image from a given path and resizes it."""
        image = nib.load(path).get_fdata()
        X = np.zeros((VOLUME_SLICES, self.img_size, self.img_size, 2))
        for j in range(VOLUME_SLICES):
            X[j,:,:,0] = cv2.resize(image[:,:,j+VOLUME_START_AT], (self.img_size, self.img_size))
        return np.array(X)

    
    def loadDataFromDir(self, path, list_of_files, mri_type, n_images):
        """ A method to load MRI and segmentation data from a directory.

        Args:
            path (_type_): _description_
            list_of_files (_type_): _description_
            mri_type (_type_): _description_
            n_images (_type_): _description_

        Returns:
            _type_: _description_
        """
        scans, masks = [], []
        for i in list_of_files[:n_images]:
            full_path = glob.glob(i + '/*' + mri_type + '*')[0]
            current_scan_volume = self.image_loader(full_path)
            current_mask_volume = self.image_loader(glob.glob(i + '/*seg*')[0])
            for j in range(current_scan_volume.shape[2]):
                scan_img = cv2.resize(current_scan_volume[:, :, j], (self.img_size, self.img_size))
                mask_img = cv2.resize(current_mask_volume[:, :, j], (self.img_size, self.img_size))
                scans.append(scan_img[..., np.newaxis])
                masks.append(mask_img[..., np.newaxis])
        return np.array(scans, dtype='float32'), np.array(masks, dtype='float32')
    
    def predictByPath(self, case_path, case):
        """Predicts the segmentation given a specific case path."""
        X = np.empty((VOLUME_SLICES, self.img_size, self.img_size, 2))
        vol_path = os.path.join(case_path, f'BraTS20_Training_{case}_flair.nii')
        flair = nib.load(vol_path).get_fdata()
        vol_path = os.path.join(case_path, f'BraTS20_Training_{case}_t1ce.nii')
        ce = nib.load(vol_path).get_fdata()
        for j in range(VOLUME_SLICES):
            X[j,:,:,0] = cv2.resize(flair[:,:,j+VOLUME_START_AT], (self.img_size, self.img_size))
            X[j,:,:,1] = cv2.resize(ce[:,:,j+VOLUME_START_AT], (self.img_size, self.img_size))
        return self.model.predict(X/np.max(X), verbose=1)
    
    def showPredictsById(self, case, start_slice=60):
        """Visualizes the predicted segmentation for a given case."""
        path = f"/home/jupyter/BraTS2020_TrainingData/MICCAI_BraTS2020_TrainingData/BraTS20_Training_{case}"
        gt = nib.load(os.path.join(path, f'BraTS20_Training_{case}_seg.nii')).get_fdata()
        origImage = nib.load(os.path.join(path, f'BraTS20_Training_{case}_flair.nii')).get_fdata()
        p = self.predictByPath(path, case)
        core, edema, enhancing = p[:,:,:,1], p[:,:,:,2], p[:,:,:,3]
        
        plt.figure(figsize=(18, 50))
        f, axarr = plt.subplots(1,6, figsize=(18, 50))
        for i in range(6):
            axarr[i].imshow(cv2.resize(origImage[:,:,start_slice+VOLUME_START_AT], (self.img_size, self.img_size)), cmap="gray", interpolation='none')
        axarr[0].title.set_text('Original image flair')
        axarr[1].imshow(cv2.resize(gt[:,:,start_slice+VOLUME_START_AT], (self.img_size, self.img_size), interpolation=cv2.INTER_NEAREST), cmap="Reds", alpha=0.3)
        axarr[1].title.set_text('Ground truth')
        axarr[2].imshow(p[start_slice,:,:,1:4], cmap="Reds", alpha=0.3)
        axarr[2].title.set_text('all classes predicted')
        axarr[3].imshow(edema[start_slice,:,:], cmap="OrRd", alpha=0.3)
        axarr[3].title.set_text('Edema predicted')
        axarr[4].imshow(core[start_slice,:,:], cmap="OrRd", alpha=0.3)
        axarr[4].title.set_text('Core predicted')
        axarr[5].imshow(enhancing[start_slice,:,:], cmap="OrRd", alpha=0.3)
        axarr[5].title.set_text('Enhancing predicted')
        plt.show()

    def predict_segmentation(self, sample_path, volume_slices=VOLUME_SLICES, volume_start_at=VOLUME_START_AT):
        """_
        """
        t1ce_path = sample_path + '_t1ce.nii'
        flair_path = sample_path + '_flair.nii'
        t1ce = nib.load(t1ce_path).get_fdata()
        flair = nib.load(flair_path).get_fdata()
        X = np.empty((volume_slices, self.img_size, self.img_size, 2))
        for j in range(volume_slices):
            X[j, :, :, 0] = cv2.resize(flair[:, :, j + volume_start_at], (self.img_size, self.img_size))
            X[j, :, :, 1] = cv2.resize(t1ce[:, :, j + volume_start_at], (self.img_size, self.img_size))
        return self.model.predict(X / np.max(X), verbose=1)
    
    def show_predicted_segmentations(self, samples_list, slice_to_plot, cmap='gray', norm=None):
        """
        Show a comparison between the ground truth and the predicted segmentation for a random sample.
        """
        # Choose a random sample from the list of samples
        random_sample = random.choice(samples_list)

        # Construct the path for the chosen patient
        random_sample_path = os.path.join(TRAIN_DATASET_PATH, random_sample, random_sample)

        # Predict the segmentation for the chosen patient
        predicted_seg = self.predict_segmentation(random_sample_path)
        
         # Load the ground truth segmentation
        seg_path = random_sample_path + '_seg.nii'
        seg = nib.load(seg_path).get_fdata()

        # Resize the ground truth segmentation to match the prediction dimensions
        seg = cv2.resize(seg[:, :, slice_to_plot + self.volume_start_at], (self.img_size, self.img_size), interpolation=cv2.INTER_NEAREST)

        # Extract the different segmentation classes from the predicted segmentation
        all_classes = predicted_seg[slice_to_plot, :, :, 1:4]  # Core, Edema, Enhancing (excluding class 0)
        background = predicted_seg[slice_to_plot, :, :, 0]     # Background (class 0)
        core = predicted_seg[slice_to_plot, :, :, 1]           # Core (class 1)
        edema = predicted_seg[slice_to_plot, :, :, 2]          # Edema (class 2)
        enhancing = predicted_seg[slice_to_plot, :, :, 3]      # Enhancing (class 3)

        # Plot the original segmentation and predicted segmentations
        print(f"Patient number: {random_sample}")
        fig, axes = plt.subplots(1, 6, figsize=(25, 20))

        # Plot the original segmentation
        axes[0].imshow(seg, cmap=cmap, norm=norm)
        axes[0].set_title('Original Segmentation')
        
        # Plot predicted segmentation for all classes
        axes[1].imshow(all_classes, cmap=cmap, norm=norm)
        axes[1].set_title('Predicted Segmentation - All Classes')

        # Plot predicted segmentation for background
        axes[2].imshow(background)
        axes[2].set_title('Predicted Segmentation - Not Tumor')

        # Plot predicted segmentation for core
        axes[3].imshow(core)
        axes[3].set_title('Predicted Segmentation - Necrotic/Core')

        # Plot predicted segmentation for edema
        axes[4].imshow(edema)
        axes[4].set_title('Predicted Segmentation - Edema')

        # Plot predicted segmentation for enhancing
        axes[5].imshow(enhancing)
        axes[5].set_title('Predicted Segmentation - Enhancing')
        
        # Adjust layout to add spacing between subplots
        plt.subplots_adjust(wspace=0.8)

        # Show the plot
        plt.show()



    def evaluate(self, test_generator):
        """Evaluates the model on the test data."""
        self.model.compile(loss="categorical_crossentropy", 
                           optimizer=tf.keras.optimizers.Adam(learning_rate=self.learning_rate), 
                           metrics=['accuracy', tf.keras.metrics.MeanIoU(num_classes=self.num_classes), 
                                    dice_coef, precision, sensitivity, specificity, 
                                    dice_coef_necrotic, dice_coef_edema, dice_coef_enhancing])
        results = self.model.evaluate(test_generator, batch_size=100)
        descriptions = ["Loss", "Accuracy", "MeanIOU", "Dice coefficient", "Precision", "Sensitivity", 
                        "Specificity", "Dice coef Necrotic", "Dice coef Edema", "Dice coef Enhancing"]
        print("\nModel evaluation on the test set:")
        print("==================================")
        for metric, description in zip(results, descriptions):
            print(f"{description} : {round(metric, 4)}")










