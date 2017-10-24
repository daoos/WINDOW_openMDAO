from openmdao.api import ExplicitComponent
from input_params import max_n_turbines
import numpy as np


class AbstractPower(ExplicitComponent):

    def setup(self):
        self.add_input('U', shape=max_n_turbines)
        self.add_input('n_turbines', val=1)

        self.add_output('p', shape=max_n_turbines)

                # Finite difference all partials.
        self.declare_partials('*', '*', method='fd')


    def compute(self, inputs, outputs):
        pass


class FarmAeroPower(ExplicitComponent):
    def setup(self):
        self.add_input('ind_powers', shape=max_n_turbines)
        self.add_input('n_turbines', val=1)

        self.add_output('farm_power', val=0.0)
                # Finite difference all partials.
        # self.declare_partials('*', '*', method='cs')


    def compute(self, inputs, outputs):
        n_turbines = int(inputs['n_turbines'])
        outputs['farm_power'] = sum(inputs['ind_powers'][:n_turbines])  # Alternative without using n_turbines. 


if __name__ == '__main__':
    from openmdao.api import Problem, Group, IndepVarComp, ExecComp

    class PowerFidelity1(AbstractPower):

        def compute(self, inputs, outputs):

            outputs['p'] = inputs['u'] ** 3.0

    model = Group()
    ivc = IndepVarComp()
    ivc.add_output('u', 7.0)
    model.add_subsystem('indep', ivc)
    model.add_subsystem('pow', PowerFidelity1())
    model.add_subsystem('equal', ExecComp('y=x+1'))

    model.connect('indep.u', 'pow.u')
    model.connect('pow.p', 'equal.x')

    prob = Problem(model)
    prob.setup()
    prob.run_model()
    print(prob['equal.y'])