import formfill

def d(**kw):
    base = {"name": "", "id": "", "autocomplete": "", "placeholder": "", "label": ""}
    return base | kw

def test_payment_fields_flagged_never_mapped():
    for f in (d(autocomplete="cc-number"), d(name="cardNumber"), d(label="CVV"),
              d(placeholder="MM/YY expiration"), d(id="securityCode")):
        assert formfill.classify(f) == "PAYMENT"

def test_profile_mapping():
    assert formfill.classify(d(autocomplete="given-name")) == "first_name"
    assert formfill.classify(d(name="lastName")) == "last_name"
    assert formfill.classify(d(label="Email Address")) == "email"
    assert formfill.classify(d(placeholder="ZIP code")) == "zip"
    assert formfill.classify(d(name="addressLine1")) == "address1"
    assert formfill.classify(d(id="billing-state")) == "state"

def test_unknown_returns_none():
    assert formfill.classify(d(name="giftMessage")) is None

def test_payment_wins_over_profile():
    assert formfill.classify(d(name="cardholderZip", label="card zip")) == "PAYMENT"
