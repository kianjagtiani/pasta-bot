"""Map checkout field descriptors to profile keys. Payment fields are only flagged."""

PAYMENT_TOKENS = ("card", "cc-", "ccnum", "cvv", "cvc", "expir", "security", "pan")

FIELD_MAP = [
    (("given-name", "first"), "first_name"),
    (("family-name", "last"), "last_name"),
    (("email",), "email"),
    (("tel", "phone"), "phone"),
    (("address-line1", "address1", "addressline1", "street"), "address1"),
    (("address-line2", "address2", "addressline2", "apt", "suite"), "address2"),
    (("postal", "zip"), "zip"),
    (("city",), "city"),
    (("state", "region", "province"), "state"),
]

GATHER_JS = """
() => Array.from(document.querySelectorAll(
        'input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select'))
    .map((el, i) => ({
        i,
        visible: el.offsetParent !== null,
        name: el.name || '',
        id: el.id || '',
        autocomplete: el.getAttribute('autocomplete') || '',
        placeholder: el.placeholder || '',
        label: (el.labels && el.labels[0] && el.labels[0].innerText) || '',
        tag: el.tagName.toLowerCase(),
        value: el.value || '',
    }))
    .filter(d => d.visible)
"""

FILL_SELECTOR = ("input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select")


def classify(desc: dict) -> str | None:
    hay = " ".join(str(desc.get(k, "")) for k in
                   ("name", "id", "autocomplete", "placeholder", "label")).lower()
    if any(t in hay for t in PAYMENT_TOKENS):
        return "PAYMENT"
    for tokens, key in FIELD_MAP:
        if any(t in hay for t in tokens):
            return key
    return None
