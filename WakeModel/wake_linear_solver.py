from openmdao.api import Group, ExplicitComponent, LinearRunOnce, LinearBlockGS, NewtonSolver, NonlinearBlockGS, DirectSolver, LinearBlockJac, IndepVarComp
from numpy import sqrt, deg2rad, tan
import numpy as np
from jensen import determine_if_in_wake, wake_radius, wake_deficit1
from order_layout import order
from ThrustCoefficient.abstract_thrust import ThrustCoefficient, FirstThrustCoefficient
from WakeModel.WakeMerge.abstract_wake_merging import WakeMergeRSS
from input_params import max_n_turbines


def distance(t1, t2, angle):
    wind_direction = deg2rad(angle)
    distance_to_centre = abs(- tan(wind_direction) * t2[1] + t2[2] + tan(wind_direction) * t1[1] - t1[2]) / sqrt(
        1.0 + tan(wind_direction) ** 2.0)
    # Coordinates of the intersection between closest path from turbine in wake to centreline.
    x_int = (t2[1] + tan(wind_direction) * t2[2] + tan(wind_direction) * (tan(wind_direction) * t1[1] - t1[2])) / \
            (tan(wind_direction) ** 2.0 + 1.0)
    y_int = (- tan(wind_direction) * (- t2[1] - tan(wind_direction) * t2[2]) - tan(
        wind_direction) * t1[1] + t1[2]) / (tan(wind_direction) ** 2.0 + 1.0)
    # Distance from intersection point to turbine
    distance_to_turbine = sqrt((x_int - t1[1]) ** 2.0 + (y_int - t1[2]) ** 2.0)
    return np.array(distance_to_turbine), np.array(distance_to_centre)


class DistanceComponent(ExplicitComponent):
    def __init__(self, number):
        super(DistanceComponent, self).__init__()
        self.number = number

    def setup(self):
        self.add_input('angle', val=90.0)
        self.add_input('layout', shape=(max_n_turbines, 3))
        self.add_input('n_turbines', val=1)
        self.add_output('dist_down', shape=max_n_turbines - 1, val=500.0)
        self.add_output('dist_cross', shape=max_n_turbines - 1, val=300.0)

        # Finite difference all partials.
        # self.declare_partials('*', '*', method='fd')

    def compute(self, inputs, outputs):
        #print "3 Distance"
        n_turbines = int(inputs['n_turbines'])
        layout = inputs['layout']
        # print layout, "Input"
        angle = inputs['angle']
        d_down = np.array([])
        d_cross = np.array([])
        for n in range(n_turbines):
            if n != self.number and self.number < n_turbines:
                d_down1, d_cross1 = distance(layout[self.number], layout[n], angle)
                d_cross = np.append(d_cross, [d_cross1])
                d_down = np.append(d_down, [d_down1])
        lendif = max_n_turbines - len(d_cross) - 1
        outputs['dist_down'] = np.concatenate((d_down, [0 for n in range(lendif)]))
        #print outputs['dist_down'], "Output1"
        outputs['dist_cross'] = np.concatenate((d_cross, [0 for n in range(lendif)]))
        #print outputs['dist_cross'], "Output2"


class DetermineIfInWakeJensen(ExplicitComponent):
    def __init__(self, number):
        super(DetermineIfInWakeJensen, self).__init__()
        self.number = number

    def setup(self):
        self.add_input('layout', shape=(max_n_turbines, 3))
        self.add_input('angle', val=90.0)
        self.add_input('n_turbines', val=1)
        self.add_input('downwind_d', shape=max_n_turbines - 1)
        self.add_input('crosswind_d', shape=max_n_turbines - 1)
        self.add_input('k', val=0.04)
        self.add_input('r', val=40.0)

        self.add_output('fraction', shape=max_n_turbines - 1, val=0)

    def compute(self, inputs, outputs):
        # print "4 Determine"
        # print inputs['layout'], "Input"
        n_turbines = int(inputs['n_turbines'])
        layout = inputs['layout']
        angle = inputs['angle']
        downwind_d = inputs['downwind_d']
        crosswind_d = inputs['crosswind_d']
        fractions = np.array([])
        k = inputs['k']
        r = inputs['r']
        i = 0
        if self.number < n_turbines:
            for n in range(n_turbines):
                if n != self.number:
                    fractions = np.append(fractions, determine_if_in_wake(layout[self.number][1], layout[self.number][2], layout[n][1], layout[n][2], angle, downwind_d[i], crosswind_d[i], r, k))
                    i += 1
        lendif = max_n_turbines - len(fractions) - 1
        outputs['fraction'] = np.concatenate((fractions, [0 for n in range(lendif)]))
        #print outputs['fraction'], "Output"


class WakeDeficit(ExplicitComponent):

    def __init__(self):
        super(WakeDeficit, self).__init__()
        self.wake_deficit = None

    def setup(self):
        self.add_input('k', val=0.04)
        self.add_input('r', val=40.0)
        self.add_input('dist_down', shape=max_n_turbines - 1, val=560.0)
        self.add_input('dist_cross', shape=max_n_turbines - 1, val=0.0)
        self.add_input('ct', shape=max_n_turbines - 1, val=0.79)
        self.add_input('fraction', shape=max_n_turbines - 1)
        self.add_input('n_turbines', val=1)
        self.add_output('dU', shape=max_n_turbines - 1, val=0.3)

    def compute(self, inputs, outputs):
        #print "5 WakeDeficit"
        n_turbines = int(inputs['n_turbines'])
        k = inputs['k']
        r = inputs['r']
        d_down = inputs['dist_down']
        d_cross = inputs['dist_cross']
        c_t = inputs['ct']
        fraction = inputs['fraction']
        #print c_t, "Input1 ct"
        #print fraction, "Input2 fraction"
        deficits = np.array([])
        for ind in range(n_turbines - 1):
            if fraction[ind] > 0.0:
                print "called"
                print ind
                deficits = np.append(deficits, [fraction[ind] * self.wake_deficit(d_down[ind], d_cross[ind], c_t[ind], k, r)])
            else:
                deficits = np.append(deficits, [0.0])
        lendif = max_n_turbines - len(deficits) - 1
        outputs['dU'] = np.concatenate((deficits, [0 for n in range(lendif)]))
        #print outputs['dU'], "Output"


class Wake(Group):
    def __init__(self, number):
        super(Wake, self).__init__()
        self.number = number

    def setup(self):
        self.add_subsystem('distance', DistanceComponent(self.number), promotes_inputs=['angle', 'layout', 'n_turbines'])
        self.add_subsystem('determine', DetermineIfInWakeJensen(self.number), promotes_inputs=['angle', 'layout', 'r', 'k', 'n_turbines'])
        self.add_subsystem('deficit', JensenWakeDeficit(), promotes_inputs=['ct', 'r', 'k', 'n_turbines'], promotes_outputs=['dU'])
        self.connect('distance.dist_down', 'determine.downwind_d')
        self.connect('distance.dist_cross', 'determine.crosswind_d')
        self.connect('distance.dist_down', 'deficit.dist_down')
        self.connect('distance.dist_cross', 'deficit.dist_cross')
        self.connect('determine.fraction', 'deficit.fraction')


class JensenWakeDeficit(WakeDeficit):
    def __init__(self):
        super(JensenWakeDeficit, self).__init__()
        self.wake_deficit = wake_deficit1


class SpeedDeficits(ExplicitComponent):

    def setup(self):
        self.add_input('dU', val=0.5)
        self.add_input('freestream', val=0.5)
        self.add_output('U', val=2.5)

    def compute(self, inputs, outputs):

        #print "8 Speed"
        dU = inputs['dU']
        freestream = inputs['freestream']
        #print dU, 'Input dU'
        outputs['U'] = np.array(freestream * (1.0 - dU))
        #print outputs['U'], "Output U"


class LinearSolveWake(Group):

    def setup(self):
        freestream = self.add_subsystem('freestream', IndepVarComp())
        freestream.add_output('freestream', val=8.5)
        self.add_subsystem('order_layout', OrderLayout(), promotes_inputs=['original', 'angle', 'n_turbines'])

        for n in range(max_n_turbines):
            self.add_subsystem('ct{}'.format(n), ThrustCoefficient(n), promotes_inputs=['n_turbines'])
            self.add_subsystem('deficits{}'.format(n), Wake(n), promotes_inputs=['angle', 'r', 'k', 'n_turbines'])
            self.add_subsystem('merge{}'.format(n), WakeMergeRSS(), promotes_inputs=['n_turbines'])
            self.add_subsystem('speed{}'.format(n), SpeedDeficits())

            self.connect('freestream.freestream', 'speed{}.freestream'.format(n))
            self.connect('order_layout.ordered', 'deficits{}.layout'.format(n))
            self.connect('ct{}.ct'.format(n), 'deficits{}.ct'.format(n))
            self.connect('deficits{}.dU'.format(n), 'merge{}.all_deficits'.format(n))
            self.connect('merge{}.sqrt'.format(n), 'speed{}.dU'.format(n))
            for m in range(max_n_turbines):
                if m != n:
                    self.connect('freestream.freestream', 'ct{}.U{}'.format(m, n))
                    # self.connect('speed{}.U'.format(n), 'ct{}.U{}'.format(m, n))
        # self.linear_solver = LinearBlockGS()
        self.nonlinear_solver = NonlinearBlockGS()
        # self.nonlinear_solver.options['maxiter'] = 30


class WakeModel(Group):

    def setup(self):
        self.add_subsystem('linear_solve', LinearSolveWake(), promotes_inputs=['r', 'k', 'original', 'angle', 'n_turbines'])
        self.add_subsystem('combine', CombineSpeed(), promotes_inputs=['n_turbines'], promotes_outputs=['U'])
        for n in range(max_n_turbines):
            self.connect('linear_solve.speed{}.U'.format(n), 'combine.U{}'.format(n))
        self.connect('linear_solve.order_layout.ordered', 'combine.ordered_layout')


class OrderLayout(ExplicitComponent):

    def setup(self):
        self.add_input('original', shape=(max_n_turbines, 3))
        self.add_input('angle', val=1.0)
        self.add_input('n_turbines', val=1)
        self.add_output('ordered', shape=(max_n_turbines, 3))

    def compute(self, inputs, outputs):
        # print "1 Order"
        n_turbines = int(inputs['n_turbines'])
        original = inputs['original'][:n_turbines]
        # print original, "Input Original layout"
        angle = inputs['angle']
        ordered = order(original, angle)
        lendif = max_n_turbines - len(original)
        if lendif > 0:
            ordered = np.concatenate((ordered, [[0 for _ in range(3)] for n in range(lendif)]))
        outputs['ordered'] = ordered
        # print ordered, "Output"

class CombineSpeed(ExplicitComponent):

    def setup(self):

        for n in range(max_n_turbines):
            self.add_input('U{}'.format(n), val=8.5)
        self.add_input('ordered_layout', shape=(max_n_turbines, 3))
        self.add_input('n_turbines', val=1)

        self.add_output('U', shape=max_n_turbines)

    def compute(self, inputs, outputs):
        n_turbines = int(inputs['n_turbines'])
        ordered_layout = inputs['ordered_layout'][:n_turbines].tolist()
        # print ordered_layout
        indices = [i[0] for i in ordered_layout]
        # print indices
        # print inputs['U0'], inputs['U1'], inputs['U2']
        final = [[indices[n], inputs['U{}'.format(int(n))][0]] for n in range(len(indices))]
        # print final
        array_speeds = [speed[1] for speed in sorted(final)]
        # print array_speeds
        lendif = max_n_turbines - len(array_speeds)
        if lendif > 0:
            array_speeds = np.concatenate((array_speeds, [0 for n in range(lendif)]))
        outputs['U'] = np.array(array_speeds)
        #print outputs['U'], "Combined Wind Speeds U"