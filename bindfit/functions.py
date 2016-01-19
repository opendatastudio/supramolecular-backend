"""
" Module containing singletons representing fitter-specific minimisation
" functions.
"
"""

from __future__ import division
from __future__ import print_function

import numpy as np
import numpy.matlib as ml

from . import helpers

import logging
logger = logging.getLogger('supramolecular')

class Function():
    def __init__(self, f):
        self.f = f

    def objective(self, params, xdata, ydata, 
                  scalar=False, 
                  detailed=False, 
                  force_molefrac=False):
        """
        Objective function:
        Performs least squares regression fitting via matrix division on provided
        NMR/UV dataset for a given binding constant K, and returns its sum of 
        least squares for optimisation OR full parameters, residuals and fitted
        results.

        Arguments:
            params: Parameter  lmfit Parameter object containing binding 
                               constant guesses
            datax:    ndarray    x x m array of x independent variables, m obs
            datay:    ndarray    y x m array of y dependent variables, m obs
            scalar:   bool       
            detailed: bool       
            molefrac: bool       Force molefraction calculation (for UV 
                                 objective functions)

        Returns:
            float:  Sum of least squares
        """

        logger.debug("Function.objective: params, xdata, ydata")
        logger.debug(params)
        logger.debug(xdata)
        logger.debug(ydata)

        # Calculate predicted HG complex concentrations for this set of 
        # parameters and concentrations
        molefrac = self.f(params, xdata, force_molefrac)

        # Solve by matrix division - linear regression by least squares
        # Equivalent to << coeffs = molefrac\ydata (EA = HG\DA) >> in Matlab
        coeffs, rssq, rank, s = np.linalg.lstsq(molefrac, ydata.T)

        # Calculate data from fitted parameters 
        # (will be normalised since input data was norm'd)
        # Result is column matrix - transform this into same shape as input
        # data array
        fit = molefrac.dot(coeffs).T

        logger.debug("Function.objective: fit")
        logger.debug(fit)

        # Calculate residuals (fitted data - input data)
        residuals = fit - ydata

        # Transpose any column-matrices to rows
        if scalar:
            return rssq.sum()
        elif detailed:
            return fit, residuals, coeffs, molefrac.T
        else:
            # scipy.leastsq requires a list
            # (returning an ndarray works for 1:1 fitters but not 1:2 - go 
            # figure)
            rsum = residuals.sum(axis=0)
            ret = [ float(r) for r in rsum ]
            logger.debug("Function.objective: residuals sum")
            logger.debug(ret)
            logger.debug(len(ret))
            return ret



#
# Function definitions
#

def nmr_1to1(params, xdata, *args, **kwargs):
    """
    Calculates predicted [HG] given data object parameters as input.
    """

    k = params[0]
    # if isinstance(params, list):
    #     k = params[0]
    # else:
    #     k = params["k"]
 
    h0 = xdata[0]
    g0 = xdata[1]

    # Calculate predicted [HG] concentration given input [H]0, [G]0 matrices 
    # and Ka guess
    hg = 0.5*(\
             (g0 + h0 + (1/k)) - \
             np.lib.scimath.sqrt(((g0+h0+(1/k))**2)-(4*((g0*h0))))\
             )

    # Replace any non-real solutions with sqrt(h0*g0) 
    inds = np.imag(hg) > 0
    hg[inds] = np.sqrt(h0[inds] * g0[inds])

    # Convert [HG] concentration to molefraction for NMR
    hg /= h0

    # Make column vector
    hg = hg.reshape(len(hg), 1)

    return hg

def uv_1to1(params, xdata, molefrac=False):
    """
    Calculates predicted [HG] given data object parameters as input.
    """

    k = params[0]
    # if isinstance(params, list):
    #     k = params[0]
    # else:
    #     k = params["k"]
 
    h0 = xdata[0]
    g0 = xdata[1]

    # Calculate predicted [HG] concentration given input [H]0, [G]0 matrices 
    # and Ka guess
    hg = 0.5*(\
             (g0 + h0 + (1/k)) - \
             np.lib.scimath.sqrt(((g0+h0+(1/k))**2)-(4*((g0*h0))))\
             )

    # Replace any non-real solutions with sqrt(h0*g0) 
    inds = np.imag(hg) > 0
    hg[inds] = np.sqrt(h0[inds] * g0[inds])

    if molefrac:
        # Convert [HG] concentration to molefraction 
        hg /= h0

    # Make column vector
    hg = hg.reshape(len(hg), 1)

    return hg

def uv_1to2(params, xdata, molefrac=False):
    """
    Calculates predicted [HG] and [HG2] given data object and binding constants
    as input.
    """

    k11 = params[0]
    k12 = params[1]
    # if isinstance(params, list):
    #     k11 = params[0]
    #     k12 = params[1]
    # else:
    #     k11 = params["k1"]
    #     k12 = params["k2"]
 
    h0 = xdata[0]
    g0 = xdata[1]

    #
    # Calculate free guest concentration [G]: solve cubic
    #
    a = np.ones(h0.shape[0])*k11*k12
    b = 2*k11*k12*h0 + k11 - g0*k11*k12
    c = 1 + k11*h0 - k11*g0
    d = -1. * g0

    # Rows: data points, cols: poly coefficients
    poly = np.column_stack((a, b, c, d))

    # Solve cubic in [G] for each observation
    g = np.zeros(h0.shape[0])
    for i, p in enumerate(poly):
        roots = np.roots(p)

        # Smallest real +ve root is [G]
        select = np.all([np.imag(roots) == 0, np.real(roots) >= 0], axis=0)
        if select.any():
            soln = roots[select].min()
            soln = float(np.real(soln))
        else:
            # No positive real roots, set solution to 0
            soln = 0.0
        
        g[i] = soln

    #
    # Calculate [HG] and [HG2] complex concentrations 
    #
    hg = h0*((g*k11)/(1+(g*k11)+(g*g*k11*k12)))
    hg2 = h0*(((g*g*k11*k12))/(1+(g*k11)+(g*g*k11*k12)))

    if molefrac:
        # Convert free concentrations to molefractions
        hg  /= h0
        hg2 /= h0

    hg_mat = np.vstack((hg, hg2))

    # Transpose for matrix calculations
    hg_mat = hg_mat.T

    return hg_mat

def nmr_1to2(params, xdata, *args, **kwargs):
    """
    Calculates predicted [HG] and [HG2] given data object and binding constants
    as input.
    """

    k11 = params[0]
    k12 = params[1]
    # if isinstance(params, list):
    #     k11 = params[0]
    #     k12 = params[1]
    # else:
    #     k11 = params["k1"]
    #     k12 = params["k2"]

    h0  = xdata[0]
    g0  = xdata[1]

    #
    # Calculate free guest concentration [G]: solve cubic
    #
    a = np.ones(h0.shape[0])*k11*k12
    b = 2*k11*k12*h0 + k11 - g0*k11*k12
    c = 1 + k11*h0 - k11*g0
    d = -1. * g0

    # Rows: data points, cols: poly coefficients
    poly = np.column_stack((a, b, c, d))

    # Solve cubic in [G] for each observation
    g = np.zeros(h0.shape[0])
    for i, p in enumerate(poly):
        roots = np.roots(p)

        # Smallest real +ve root is [G]
        select = np.all([np.imag(roots) == 0, np.real(roots) >= 0], axis=0)
        if select.any():
            soln = roots[select].min()
            soln = float(np.real(soln))
        else:
            # No positive real roots, set solution to 0
            soln = 0.0
        
        g[i] = soln


    #
    # Calculate [HG] and [HG2] complex concentrations 
    #
    hg = (g*k11)/(1+(g*k11)+(g*g*k11*k12))
    hg2 = ((g*g*k11*k12))/(1+(g*k11)+(g*g*k11*k12))

    hg_mat = np.vstack((hg, hg2))


    # Transpose for matrix calculations
    hg_mat = hg_mat.T

    return hg_mat

def nmr_2to1(params, xdata, *args, **kwargs):
    """
    Calculates predicted [HG] and [H2G] given data object and binding constants
    as input.
    """

    k11 = params[0]
    k12 = params[1]
    h0  = xdata[0]
    g0  = xdata[1]

    #
    # Calculate free host concentration [H]: solve cubic
    #
    a = np.ones(h0.shape[0])*k11*k12
    b = 2*k11*k12*g0 + k11 - h0*k11*k12
    c = 1 + k11*g0 - k11*h0
    d = -1. * h0

    # Rows: data points, cols: poly coefficients
    poly = np.column_stack((a, b, c, d))

    # Solve cubic in [H] for each observation
    h = np.zeros(h0.shape[0])

    for i, p in enumerate(poly):
        roots = np.roots(p)
        # Smallest real +ve root is [H]
        select = np.all([np.imag(roots) == 0, np.real(roots) >= 0], axis=0)
        if select.any():
            soln = roots[select].min()
            soln = float(np.real(soln))
        else:
            # No positive real roots, set solution to 0
            soln = 0.0

        h[i] = soln

    #
    # Calculate [HG] and [H2G] complex concentrations 
    #
    hg = (g0*h*k11)/(h0*(1+(h*k11)+(h*h*k11*k12)))
    h2g = (2*g0*h*h*k11*k12)/(h0*(1+(h*k11)+(h*h*k11*k12)))

    hg_mat = np.vstack((hg, h2g))

    # Transpose for matrix calculations
    hg_mat = hg_mat.T

    return hg_mat

def uv_2to1(params, xdata, molefrac=False):
    """
    Calculates predicted [HG] and [H2G] given data object and binding constants
    as input.
    """

    # Convenience
    k11 = params[0]
    k12 = params[1]
    h0  = xdata[0]
    g0  = xdata[1]

    #
    # Calculate free host concentration [H]: solve cubic
    #
    a = np.ones(h0.shape[0])*k11*k12
    b = 2*k11*k12*g0 + k11 - h0*k11*k12
    c = 1 + k11*g0 - k11*h0
    d = -1. * h0

    # Rows: data points, cols: poly coefficients
    poly = np.column_stack((a, b, c, d))

    # Solve cubic in [H] for each observation
    h = np.zeros(h0.shape[0])

    for i, p in enumerate(poly):
        roots = np.roots(p)
        # Smallest real +ve root is [H]
        select = np.all([np.imag(roots) == 0, np.real(roots) >= 0], axis=0)
        if select.any():
            soln = roots[select].min()
            soln = float(np.real(soln))
        else:
            # No positive real roots, set solution to 0
            soln = 0.0

        h[i] = soln

    #
    # Calculate [HG] and [H2G] complex concentrations 
    #
    hg = g0*((h*k11)/(1+(h*k11)+(h*h*k11*k12)))
    h2g = g0*((2*h*h*k11*k12)/(1+(h*k11)+(h*h*k11*k12)))

    if molefrac:
        # Convert free concentrations to molefractions
        hg  /= h0
        h2g /= h0

    hg_mat = np.vstack((hg, h2g))

    # Transpose for matrix calculations
    hg_mat = hg_mat.T

    return hg_mat



# Initialise singletons for each function
# Reference by dict key, ultimately exposed to use by formatter.fitter_list 
# dictionary
select = {
        "nmr1to1": Function(nmr_1to1),
        "nmr1to2": Function(nmr_1to2),
        "nmr2to1": Function(nmr_2to1),
        "uv1to1" : Function(uv_1to1),
        "uv1to2" : Function(uv_1to2),
        "uv2to1" : Function(uv_2to1),
        }
