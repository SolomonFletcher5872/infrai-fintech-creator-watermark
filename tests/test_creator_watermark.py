from src.creator_watermark import PaymentEvent, decide_publish


def test_publish_requires_a_positive_payment_with_a_reference():
    confirmed = PaymentEvent("creator-7", "portrait.png", 1800, "pay_7")
    missing_payment = PaymentEvent("creator-7", "portrait.png", 0, "pay_7")
    missing_reference = PaymentEvent("creator-7", "portrait.png", 1800, " ")

    assert decide_publish(confirmed).allowed is True
    assert decide_publish(missing_payment).reason == "payment must be positive"
    assert decide_publish(missing_reference).reason == "payment reference is required"
