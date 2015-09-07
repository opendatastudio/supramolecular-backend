from __future__ import division
from __future__ import print_function

from django.db import models
from django.contrib.postgres.fields import ArrayField

import numpy as np
import numpy.matlib as ml
import hashlib
import uuid

from . import formatter 

class Data(models.Model):
    id = models.CharField(max_length=40, primary_key=True)
    h0 = ArrayField(models.FloatField())
    g0 = ArrayField(models.FloatField())
    y = ArrayField(
            ArrayField(models.FloatField())
            )

    @classmethod
    def from_csv(cls, f):
        raw = np.loadtxt(f, delimiter=",", skiprows=1)

        # Use SHA1 hash of array as primary key to avoid duplication
        hasher = hashlib.sha1()
        hasher.update(raw)
        id = hasher.hexdigest()

        h0 = list(raw[:,0])
        g0 = list(raw[:,1])

        y_raw = raw[:,2:]
        y = [ list(y_raw[:,col]) for col in range(y_raw.shape[1]) ]

        return cls(id=id, h0=h0, g0=g0, y=y)

    def to_dict(self):
        h0 = np.array(self.h0)
        g0 = np.array(self.g0)
        y = np.array(self.y)

        geq = g0/h0

        # Calculate normalised y
        # Transpose magic for easier repmat'n
        initialmat = ml.repmat(y.T[0,:], len(y.T), 1)
        ynorm = (y.T - initialmat).T

        data = {
                "h0": h0,
                "g0": g0,
                "geq": geq,
                "y": y,
                "ynorm": ynorm,
                }

        return data

class Fit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Metadata
    name = models.CharField(max_length=200, blank=True)
    notes = models.CharField(max_length=10000, blank=True)

    # Link to raw data used for fit
    data = models.ForeignKey(Data)

    # Fit options 
    fitter = models.CharField(max_length=20)
    params_guess = ArrayField(base_field=models.FloatField())

    params = ArrayField(base_field=models.FloatField())
    y = ArrayField(
            ArrayField(models.FloatField())
            )

    def to_dict(self):
        data_dict = self.data.to_dict()

        fit_dict = {
                "metadata": {
                    "name"   : self.name,
                    "notes"  : self.notes,
                    },
                "options": {
                    "fitter" : self.fitter,
                    "params" : [ {"value": p} for p in self.params_guess ],
                    "data_id": self.data_id,
                    },
                "result": formatter.fit(fitter=self.fitter,
                                    data=data_dict,
                                    fit=np.array(self.y),
                                    params=self.params,
                                    residuals=None)
                }

        return fit_dict
