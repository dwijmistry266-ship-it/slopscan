"""Example sloppy file. Deliberately bad — used for the README demo.

Do not "fix" this file; slopscan's demo output is generated from it.
"""

import os
import sys
import json  # never used anywhere below
import re  # noqa  (this one is fine, leave it alone)


# This is a great and amazing function, perfect in every way!
def calculate_total(items):
    # TODO: handle discounts properly later
    total = 0
    for item in items:
        total += item
    # return the total
    return total
    print("this never runs")


def unfinished_thing():
    ...


def another_unfinished():
    pass


def not_done_yet():
    # will be implemented later, coming soon
    raise NotImplementedError


# def old_calculate_total(items):
#     total = 0
#     for item in items:
#         total = total + item
#     return total


def process_users(users):
    result = []
    for user in users:
        if user.active:
            if user.verified:
                if user.balance > 0:
                    if not user.banned:
                        if user.country == "IN":
                            result.append(user.name)
    return result


def _format_name(name):
    return name.strip().title()


def greet(name):
    return "hello " + _format_name(name)


class Greeter:
    def __init__(self, greeting):
        self.greeting = greeting

    def greet(self, name):
        return f"{self.greeting}, {name}"


def fetch_data(source):
    # hallucinated API that was never imported or defined
    client = make_client(source)
    return client.stream_response()


def validate_a(data):
    if data is None:
        return False
    if not isinstance(data, dict):
        return False
    if "name" not in data:
        return False
    if not data["name"]:
        return False
    return True


def validate_b(data):
    if data is None:
        return False
    if not isinstance(data, dict):
        return False
    if "email" not in data:
        return False
    if not data["email"]:
        return False
    return True


def long_function():
    x = 1
    y = 2
    z = 3
    a = x + y + z
    b = a * 2
    c = b - 1
    d = c + 10
    e = d * 3
    f = e - 5
    g = f + 7
    h = g * 2
    i = h - 3
    j = i + 11
    k = j * 2
    l = k - 9
    m = l + 4
    n = m * 2
    o = n - 6
    p = o + 8
    q = p * 2
    r = q - 2
    s = r + 12
    t = s * 2
    u = t - 4
    v = u + 6
    w = v * 2
    ab = w - 8
    ac = ab + 9
    ad = ac * 2
    ae = ad - 1
    af = ae + 13
    ag = af * 2
    ah = ag - 7
    ai = ah + 2
    aj = ai * 2
    ak = aj - 3
    al = ak + 14
    am = al * 2
    an = am - 5
    ao = an + 1
    ap = ao * 2
    aq = ap - 11
    ar = aq + 16
    unused_var = 42
    return ar
