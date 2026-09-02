import tensorflow as tf
from tensorflow.keras import layers, models, applications, callbacks
import matplotlib.pyplot as plt
import os
import ssl

# Fix for macOS SSL CERTIFICATE_VERIFY_FAILED error
ssl._create_default_https_context = ssl._create_unverified_context

DATASET_DIR = 'dataset'
BATCH_SIZE = 32
IMAGE_SIZE = (224, 224)
INITIAL_EPOCHS = 10
FINE_TUNE_EPOCHS = 10
TOTAL_EPOCHS = INITIAL_EPOCHS + FINE_TUNE_EPOCHS

def main():
    print("1. Loading EcoSort Waste Dataset...")
    
    if not os.path.exists(DATASET_DIR) or len(os.listdir(DATASET_DIR)) == 0:
        print(f"Error: Dataset directory '{DATASET_DIR}' is empty. Please add images to trash/, recycling/, and compost/ folders.")
        return

    train_ds = tf.keras.utils.image_dataset_from_directory(
        DATASET_DIR,
        validation_split=0.2,
        subset="training",
        seed=123,
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE
    )

    val_ds = tf.keras.utils.image_dataset_from_directory(
        DATASET_DIR,
        validation_split=0.2,
        subset="validation",
        seed=123,
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE
    )

    class_names = train_ds.class_names
    print(f"Found {len(class_names)} classes: {class_names}")
    
    with open('labels.txt', 'w') as f:
        f.write('\n'.join(class_names))

    AUTOTUNE = tf.data.AUTOTUNE
    train_ds = train_ds.cache().shuffle(1000).prefetch(buffer_size=AUTOTUNE)
    val_ds = val_ds.cache().prefetch(buffer_size=AUTOTUNE)

    print("\n2. Building Smart Bin Edge Model (MobileNetV2 Transfer Learning)...")
    preprocess_input = tf.keras.applications.mobilenet_v2.preprocess_input
    
    data_augmentation = tf.keras.Sequential([
        layers.RandomFlip('horizontal_and_vertical'),
        layers.RandomRotation(0.3),
        layers.RandomZoom(0.3),
        layers.RandomTranslation(height_factor=0.2, width_factor=0.2),
        layers.RandomBrightness(0.2),
        layers.RandomContrast(0.2),
    ])

    base_model = applications.MobileNetV2(
        input_shape=IMAGE_SIZE + (3,),
        include_top=False,
        weights='imagenet'
    )
    base_model.trainable = False 

    inputs = tf.keras.Input(shape=IMAGE_SIZE + (3,))
    x = data_augmentation(inputs)
    x = preprocess_input(x)
    x = base_model(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.2)(x)
    outputs = layers.Dense(len(class_names), activation='softmax')(x)

    model = tf.keras.Model(inputs, outputs)

    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                  loss=tf.keras.losses.SparseCategoricalCrossentropy(),
                  metrics=['accuracy'])

    early_stopping = callbacks.EarlyStopping(
        monitor='val_loss', 
        patience=6,
        restore_best_weights=True,
        verbose=1
    )

    print("\n3. Phase 1: Training the top classification layer...")
    history_1 = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=INITIAL_EPOCHS,
        callbacks=[early_stopping]
    )

    print("\n4. Phase 2: Fine-Tuning the base model for waste detection...")
    base_model.trainable = True
    for layer in base_model.layers[:-30]:
        layer.trainable = False

    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
                  loss=tf.keras.losses.SparseCategoricalCrossentropy(),
                  metrics=['accuracy'])

    history_2 = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=TOTAL_EPOCHS,
        initial_epoch=history_1.epoch[-1] + 1,
        callbacks=[early_stopping]
    )

    print("\n5. Saving the EcoSort model...")
    model.save('ecosort_model.keras')
    print("Model saved as 'ecosort_model.keras'")

if __name__ == '__main__':
    main()
