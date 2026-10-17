"""Placeholder notification module for cloud CI."""
class NotificationSound:
    BIRDSONG = "birdsong"

def send_notification(*args, **kwargs):
    print("[notification]", args, kwargs)

