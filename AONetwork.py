import keras
from keras.models import Model
from keras.layers import Input, Concatenate, Conv2D, MaxPooling2D, Conv2DTranspose, Dropout
from keras import backend as K

def UNet(input_shape=(256, 256, 1), kernel_size=(3, 3), kernel_init='he_normal', output_class=1):
    n_ch_exps = [4, 5, 6, 7, 8, 9]

    if K.image_data_format() == 'channels_first':
        ch_axis = 1
        input_shape = (1, input_shape[0], input_shape[1])
    elif K.image_data_format() == 'channels_last':
        ch_axis = 3

    inp = Input(shape=input_shape)
    encodeds = []

    # encoder
    enc = inp
    for l_idx, n_ch in enumerate(n_ch_exps):
        enc = Conv2D(filters=2 ** n_ch, kernel_size=kernel_size, activation='relu', padding='same',
                     kernel_initializer=kernel_init)(enc)
        enc = Dropout(0.1*l_idx)(enc)
        enc = Conv2D(filters=2**n_ch, kernel_size=kernel_size, activation='relu', padding='same',
                     kernel_initializer=kernel_init)(enc)
        encodeds.append(enc)

        if n_ch < n_ch_exps[-1]:
            enc = MaxPooling2D(pool_size=(2,2))(enc)

    # decoder
    dec = enc
    decoder_n_chs = n_ch_exps[::-1][1:]
    for l_idx, n_ch in enumerate(decoder_n_chs):
        l_idx_rev = len(n_ch_exps) - l_idx - 2  #
        dec = Conv2DTranspose(filters=2 ** n_ch, kernel_size=kernel_size, strides=(2, 2), activation='relu',
                              padding='same', kernel_initializer=kernel_init)(dec)
        dec = Concatenate(axis=ch_axis)([dec, encodeds[l_idx_rev]])
        dec = Conv2D(filters=2 ** n_ch, kernel_size=kernel_size, activation='relu', padding='same',
                     kernel_initializer=kernel_init)(dec)
        dec = Dropout(0.1 * l_idx)(dec)
        dec = Conv2D(filters=2 ** n_ch, kernel_size=kernel_size, activation='relu', padding='same',
                     kernel_initializer=kernel_init)(dec)

    outp = Conv2DTranspose(filters=output_class, kernel_size=kernel_size, activation='sigmoid', padding='same',
                           kernel_initializer='glorot_normal')(dec)

    model = Model(inputs=[inp], outputs=[outp])
    return model