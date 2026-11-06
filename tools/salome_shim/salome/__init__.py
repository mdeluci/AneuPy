"""Minimal stand-in for the ``salome`` package (study and GUI are no-ops)."""


class _Study:
    def SaveAs(self, *args, **kwargs):
        return True


class _Gui:
    def updateObjBrowser(self, *args, **kwargs):
        return None


myStudy = _Study()
sg = _Gui()


def salome_init(*args, **kwargs):
    return None
