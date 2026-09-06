"""Persist a complete enrollment step before applying any of its writes."""

from repaso.schemas.enrollment import EnrollmentProgress
from repaso.schemas.family import Family
from repaso.schemas.student import Student

MODELS = {"put_enrollment": EnrollmentProgress, "put_family": Family, "put_student": Student}


class EnrollmentWrites:
    def __init__(self):
        self.actions = []

    def _put(self, method, model):
        self.actions.append({"method": method, "document": model.model_dump(mode="json")})

    def put_enrollment(self, model):
        self._put("put_enrollment", model)

    def put_family(self, model):
        self._put("put_family", model)

    def put_student(self, model):
        self._put("put_student", model)

    def delete_enrollment(self, channel, chat_ref):
        self.actions.append({"method": "delete_enrollment", "args": [channel, chat_ref]})


def apply_step(store, record):
    if record.payload.get("applied"):
        return
    for action in record.payload["actions"]:
        method = action["method"]
        if method in MODELS:
            getattr(store, method)(MODELS[method].model_validate(action["document"]))
        elif method == "delete_enrollment":
            store.delete_enrollment(*action["args"])
        else:
            raise ValueError("invalid enrollment journal operation")
    record.payload["applied"] = True
    store.put_record(record)
