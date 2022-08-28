class NotificationException(Exception):
    """
    A small class that defines a Notification Exception.
    """
    def __init__(self, message):
        self.value = str(message)
        Exception.__init__(self, self.value)

    def __str__(self):
        return self.value
