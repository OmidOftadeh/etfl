from collections import namedtuple
import pandas as pd
import numpy  as np

from etfl.io.json import load_json_model
from etfl.optim.config import standard_solver_config, growth_uptake_config

from etfl.optim.variables import GrowthActivation, BinaryActivator

from time import time
from copy import copy


try:
    from gurobipy import GRB
except ModuleNotFoundError:
    pass

solver = 'optlang-gurobi'

DefaultSol = namedtuple('DefaultSol', field_names='f')


def is_gurobi(model):
    return model.problem.__name__ == 'optlang.gurobi_interface'

def fix_growth(model, solution = None):

    solution = check_solution(model, solution)

    mu_variables = model.get_variables_of_type(GrowthActivation)
    interp_variables = model.get_variables_of_type(BinaryActivator)

    vars_to_fix = list(mu_variables) + list(interp_variables)

    gurobi_hints = is_gurobi(model)
    if gurobi_hints:
        model.logger.info('Gurobi-based model detected - using  Gurobi hints')

    for the_var in vars_to_fix:
        value = solution.raw[the_var.name]
        try:
            the_var.variable.lb = int(value)
            the_var.variable.ub = int(value)
        except ValueError:
            # Happens if lb>ub during assignment
            the_var.variable.ub = int(value)
            the_var.variable.lb = int(value)

        if gurobi_hints:
            the_var.variable._internal_variable.VarHintVal = value
            the_var.variable._internal_variable.VarHintPri = 5


def check_solution(model, solution):
    if solution is None:
        try:
            solution = model.solution
        except AttributeError:
            raise AttributeError('If not providing a solution object, please '
                                 'provide a model with an embedded solution '
                                 '(call model.solve())')
    return solution


def release_growth(model):

    mu_variables = model.get_variables_of_type(GrowthActivation)
    interp_variables = model.get_variables_of_type(BinaryActivator)

    vars_to_fix = list(mu_variables) + list(interp_variables)

    gurobi_hints = is_gurobi(model)
    for the_var in vars_to_fix:
        the_var.variable.lb = 0
        the_var.variable.ub = 1

        if gurobi_hints:
            the_var.variable._internal_variable.VarHintVal = GRB.UNDEFINED
            the_var.variable._internal_variable.VarHintPri = 0

def apply_warm_start(model, solution):
    solution = check_solution(model, solution)

    for the_var in model.variables:
        if the_var.type == 'binary':
            the_var._internal_variable.Start = solution.raw[the_var.name]

def release_warm_start(model):

    for the_var in model.variables:
        if the_var.type == 'binary':
            the_var._internal_variable.Start = GRB.UNDEFINED

def get_active_growth_bounds(model):
    mu = model.growth_reaction.flux
    difflist = [abs(mu - x[0]) for x in model.mu_bins]
    min_diff = min(difflist)
    min_ix = difflist.index(min_diff)

    mu_i, (mu_lb, mu_ub) = model.mu_bins[min_ix]

    return mu_i, mu_lb, mu_ub

def safe_optim(model):
    try:
        out = model.optimize()
    except Exception:
        model.logger.warning('Solver status: {}'.format(model.solver.status))
        out = DefaultSol
        out.f = np.nan
    return  out

def _va_sim(model):
    model.objective.direction = 'max'
    sol_max = safe_optim(model)

    model.objective.direction = 'min'
    sol_min = safe_optim(model)

    return sol_min, sol_max


def simulate(available_uptake, model, variables, warm_start=None):

    model.logger.info('available_uptake = {}'.format(available_uptake))
    model.reactions.EX_glc__D_e.lower_bound = available_uptake
    model.growth_reaction.lower_bound = 0
    model.growth_reaction.upper_bound = 10

    model.objective = model.growth_reaction.id
    model.objective.direction = 'max'

    out = safe_optim(model)
    growth_solution = copy(model.solution)

    if model.solver.status == 'infeasible':
        ret = {'obj':np.nan,
               'mu': np.nan,
               'mu_lb':np.nan,
               'mu_ub':np.nan,
               'available_substrate':available_uptake,
               'uptake':np.nan,
               'prot_ratio':np.nan,
               'mrna_ratio':np.nan
               }
        for var in variables:
            ret[var + '_lb'] = np.nan
            ret[var + '_ub'] = np.nan
        print('INFEASIBLE SOLUTION AT q={}'.format(available_uptake))
        return pd.Series(ret)

    mu_i, mu_lb, mu_ub = get_active_growth_bounds(model)
    mu = model.growth_reaction.flux
    release_warm_start(model)

    try:
        prot_ratio = model.interpolation_variable.prot_ggdw.variable.primal
        mrna_ratio = model.interpolation_variable.mrna_ggdw.variable.primal
    except AttributeError:
        # Model without Neidhardt data
        prot_ratio = np.nan
        mrna_ratio = np.nan


    ret = {'obj':model.solution.f,
           'mu': mu,
           'mu_lb':mu_lb,
           'mu_ub':mu_ub,
           'available_substrate':-1*available_uptake,
           'uptake':-1*growth_solution.fluxes['EX_glc__D_e'],
           'prot_ratio':prot_ratio,
           'mrna_ratio':mrna_ratio
           }

    fix_growth(model, model.solution)

    for var in variables:
        model.objective = model.variables.get(var)

        lb, ub = _va_sim(model)

        ret[var + '_lb'] = lb.f
        ret[var + '_ub'] = ub.f

    print(pd.Series(ret))

    release_growth(model)
    apply_warm_start(model, growth_solution)

    return pd.Series(ret)

if __name__ == '__main__':
    # Do things

    variables = [
                'EZ_rib',
                'EZ_rnap',
                # 'EZ_dummy_enzyme',
                # 'MR_dummy_gene',
                 ]


    # uptake_range = pd.Series(np.arange(-1,-40, -1))
    uptake_range = pd.Series(np.arange(-1,-25, -1))

    model_files = {
        # 'EFL':'iJO1366_EFL_431_enz_128_bins__20190108_172213.json',
        # 'ETFL':'RelaxedModel iJO1366_ETFL_431_enz_128_bins__20190108_173057.json',
        # 'vEFL':'iJO1366_vEFL_431_enz_128_bins__20190108_180140.json',
        # 'vETFL':'RelaxedModel iJO1366_vETFL_431_enz_128_bins__20190108_181346.json',
        # 'vETFL65':'SlackModel iJO1366_vETFL_431_enz_128_bins__20190110_134145.json',
        'vETFL_infer':'SlackModel iJO1366_vETFL_2084_enz_128_bins__20190110_134830.json',
        'vETFL65_infer':'SlackModel iJO1366_vETFL_2084_enz_128_bins__20190110_182855.json',
    }

    models = {k:load_json_model('models/'+v,solver=solver) for k,v in model_files.items()}
    data = {}

    for name,model in models.items():
        growth_uptake_config(model)
        model.warm_start = None
        model.logger.info('Simulating ...')
        start = time()
        data[name] = uptake_range.apply(simulate, args=[model,variables])
        stop = time()
        print('Elapsed time: {}'.format(stop - start))
        data[name].to_csv('outputs/benchmark_{}.csv'.format(name))
