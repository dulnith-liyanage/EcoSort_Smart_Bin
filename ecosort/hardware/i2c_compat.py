"""
Pi I2C buffer normalization for compatibility with Adafruit Blinka and PureIO.
"""

class BufferCompatibleI2C:
    """Retain transfer slicing/locking while normalising outgoing memoryviews.

    Blinka's Linux backend forwards memoryviews to PureIO 1.1.11, whose
    combined-read register argument only accepts bytes, bytearray or an int.
    This adapter affects only the ServoKit bus, not installed library files.
    """
    def __init__(self, bus):
        self.bus = bus

    def __getattr__(self, name):
        return getattr(self.bus, name)

    def writeto_then_readfrom(self, address, buffer_out, buffer_in, **kwargs):
        return self.bus.writeto_then_readfrom(
            address, bytes(buffer_out), buffer_in, **kwargs)


def prepare_servo_kit(kit):
    """
    Ensure the ServoKit instance uses BufferCompatibleI2C for hardware compatibility.
    """
    # ServoKit has no public bus accessor after construction. Limit this
    # compatibility adapter to the PCA9685 I2CDevice; test doubles need none.
    pca = getattr(kit, '_pca', None)
    if pca is not None:
        device = pca.i2c_device
        if not isinstance(device.i2c, BufferCompatibleI2C):
            device.i2c = BufferCompatibleI2C(device.i2c)
    return kit
