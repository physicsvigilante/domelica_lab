#!/usr/bin/env python3
"""Verify the native cart-pendulum-spring run against an independent nonlinear IVP.

The constants and Lagrange equations below are an independent test definition.
They do not generate viewer samples. The unchanged M4 reader binds native CSV
samples to fresh MAT, simulation log, visual XML and completion evidence.
Only --reference-only can run without native simulation results, and it does
not claim a native verification result.
"""

import argparse
import json
import math

from verify_m4 import dot, read_case, require_close, track, vector

CASE_PREFIX = "m4c_cart_pendulum"
STOP_TIME = 6.0
MINIMUM_SAMPLES = 1201
MODEL_NAME = "DomelicaLab.Examples.CartPendulumSpring3D"

# Independent nominal definition, never loaded from Modelica output.
M, m, L, k, g = 2.0, 1.0, 1.0, 20.0, 10.0
THETA0 = 35.0 * math.pi / 180.0
FREE_LENGTH = 1.1
CART_LENGTH, CART_WIDTH, CART_HEIGHT, CART_Y = 0.5, 0.32, 0.2, 1.6
PIVOT_Y = CART_Y - CART_HEIGHT / 2.0
BOB_DIAMETER, ROD_DIAMETER = 0.18, 0.035
INITIAL_STATE = (0.0, 0.0, THETA0, 0.0, 0.0)
INITIAL_ENERGY = M*g*CART_Y + m*g*(PIVOT_Y-L*math.cos(THETA0))


def required_columns():
    scalars = ["time", "cartDisplacement", "cartSpeed", "cartAcceleration",
        "pendulumAngle", "pendulumSpeed", "pendulumAcceleration", "springLength",
        "springExtension", "springForce", "rodTension", "rodPower", "guidePower",
        "springPower", "horizontalMomentum", "springImpulse", "kineticEnergy",
        "gravitationalEnergy", "elasticEnergy", "totalEnergy", "cartGuide.s",
        "cartGuide.v", "cartGuide.a", "hinge.phi", "hinge.w", "hinge.a", "hinge.tau",
        "cartMass", "bobMass", "rodLength", "springStiffness", "springFreeLength", "g",
        "initialAngle", "cartLength", "cartWidth", "cartHeight", "cartCenterHeight",
        "bobDiameter", "rodDiameter", "cartBody.m", "cartBody.density", "cartBody.innerWidth",
        "cartBody.innerHeight", "bob.m", "wallSpring.c", "wallSpring.s_unstretched",
        "wallSpring.m", "wallSpring.length", "wallSpring.f", "wallSpring.width",
        "wallSpring.coilWidth", "wallSpring.numberOfWindings"]
    vectors = ("cartPosition", "pivotPosition", "bobPosition", "cartVelocity", "bobVelocity",
        "bobAcceleration", "cartAngularVelocity", "centerOfMass", "springAnchorPosition",
        "springCartPosition", "springForceOnCart", "rodForceOnBob", "pendulumForceOnCart",
        "railReaction", "railTorque", "cartBody.frame_a.r_0", "cartBody.v_0", "cartBody.a_0",
        "cartBody.r_CM", "cartBody.body.w_a", "cartBody.body.z_a", "cartBody.frame_a.t",
        "bob.frame_a.r_0", "bob.v_0", "bob.a_0", "bob.frame_a.f", "bob.frame_a.t",
        "cartGuide.frame_a.r_0", "cartGuide.frame_b.r_0", "cartGuide.frame_b.f",
        "cartGuide.frame_b.t", "hinge.frame_a.r_0", "hinge.frame_a.f", "hinge.frame_a.t",
        "hinge.frame_b.f", "hinge.frame_b.t", "rod.frame_a.r_0", "rod.frame_b.r_0",
        "rod.frame_a.f", "rod.frame_b.f", "rod.frame_a.t", "rod.frame_b.t", "rod.r",
        "wallSpring.frame_a.r_0", "wallSpring.frame_b.r_0", "wallSpring.frame_a.f",
        "wallSpring.frame_b.f", "cartGuide.n", "hinge.n")
    matrices = ("cartBody.I", "cartBody.frame_a.R.T", "rod.frame_a.R.T")
    return scalars + [f"{name}[{axis}]" for name in vectors for axis in (1,2,3)] + [
        f"{name}[{i},{j}]" for name in matrices for i in (1,2,3) for j in (1,2,3)]


def nonlinear_accelerations(x, theta, omega):
    """Solve the independently derived symmetric 2x2 Lagrange mass matrix."""
    s, c = math.sin(theta), math.cos(theta)
    a11, a12, a22 = M+m, m*L*c, m*L*L
    b1, b2 = m*L*s*omega*omega-k*x, -m*g*L*s
    determinant = a11*a22-a12*a12
    if determinant <= 0.0:
        raise AssertionError("The independent mass matrix must be positive definite")
    return ((b1*a22-a12*b2)/determinant, (a11*b2-a12*b1)/determinant)


def reference_rhs(state):
    x, v, theta, omega, _ = state
    a, alpha = nonlinear_accelerations(x, theta, omega)
    return (v, a, omega, alpha, -k*x)


def reference_energy(state):
    x, v, theta, omega, _ = state
    kinetic = ((M+m)*v*v + 2*m*L*math.cos(theta)*v*omega + m*L*L*omega*omega)/2.0
    return kinetic + M*g*CART_Y + m*g*(PIVOT_Y-L*math.cos(theta)) + k*x*x/2.0


def integrate_reference(times, maximum_step, subdivisions=1):
    """Classic RK4, landing exactly on each requested native output time."""
    if maximum_step <= 0.0 or subdivisions<1 or not times or abs(times[0]) > 1e-12:
        raise ValueError("Reference integration needs positive steps and time beginning at zero")
    current_time, state, output = 0.0, tuple(INITIAL_STATE), []
    for target in times:
        span = target-current_time
        if span < -1e-12:
            raise ValueError("Reference times must be ordered")
        count = max(1, math.ceil(span/maximum_step))*subdivisions
        step = span/count
        for _ in range(count):
            a = reference_rhs(state)
            b = reference_rhs(tuple(s+step*d/2.0 for s,d in zip(state,a)))
            c = reference_rhs(tuple(s+step*d/2.0 for s,d in zip(state,b)))
            d = reference_rhs(tuple(s+step*q for s,q in zip(state,c)))
            state = tuple(s+step*(u+2*v+2*w+z)/6.0 for s,u,v,w,z in zip(state,a,b,c,d))
        current_time = target
        output.append(state)
    return output


def checked_reference(times):
    coarse = integrate_reference(times, 0.002)
    # Exactly halve every coarse interval; both runs land on all output times.
    fine = integrate_reference(times, 0.002, subdivisions=2)
    names = ("cartPosition_m", "cartVelocity_m_s", "pendulumAngle_rad",
        "pendulumVelocity_rad_s", "externalImpulse_N_s")
    convergence = {name: max(abs(a[i]-b[i]) for a,b in zip(coarse,fine))
        for i,name in enumerate(names)}
    for name,error in convergence.items():
        require_close(error,0.0,1e-8,"Independent RK4 step-halving "+name)
    energy_error = max(abs(reference_energy(s)-INITIAL_ENERGY) for s in fine)
    impulse_error = max(abs((M+m)*s[1]+m*L*math.cos(s[2])*s[3]-s[4]) for s in fine)
    require_close(energy_error,0.0,1e-8,"Independent reference energy")
    require_close(impulse_error,0.0,1e-8,"Independent reference momentum-impulse")
    return fine, {"method":"RK4 with independently derived 2x2 nonlinear mass matrix",
        "coarseMaximumStep_s":0.002,"fineMaximumStep_s":0.001,
        "stepHalvingMaximumDifferences":convergence,"maximumEnergyDrift_J":energy_error,
        "maximumMomentumImpulseResidual_N_s":impulse_error,
        "convergenceAcceptance":1e-8,
        "note":"Step halving and balance checks support numerical accuracy; they are not a rigorous global-error bound."}


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def to_world(local, theta):
    c, s = math.cos(theta), math.sin(theta)
    return [c*local[0]-s*local[1], s*local[0]+c*local[1], local[2]]


def negative(v):
    return [-x for x in v]


def compare_vector(maxima, name, actual, expected, tolerance, time):
    for a,b in zip(actual,expected):
        track(maxima,name,a,b,tolerance,time)


def verify_cart():
    rows = read_case(CASE_PREFIX,STOP_TIME,MINIMUM_SAMPLES,required_columns())
    reference, reference_report = checked_reference([r["time"] for r in rows])
    parameters = {"cartMass":M,"bobMass":m,"rodLength":L,"springStiffness":k,
        "springFreeLength":FREE_LENGTH,"g":g,"initialAngle":THETA0,
        "cartLength":CART_LENGTH,"cartWidth":CART_WIDTH,"cartHeight":CART_HEIGHT,
        "cartCenterHeight":CART_Y,"bobDiameter":BOB_DIAMETER,"rodDiameter":ROD_DIAMETER,
        "cartBody.m":M,"cartBody.density":M/(CART_LENGTH*CART_WIDTH*CART_HEIGHT),
        "cartBody.innerWidth":0.0,"cartBody.innerHeight":0.0,"bob.m":m,
        "wallSpring.c":k,"wallSpring.s_unstretched":FREE_LENGTH,"wallSpring.m":0.0,
        "wallSpring.width":0.06,"wallSpring.coilWidth":0.005,"wallSpring.numberOfWindings":12.0}
    inertia = [M*(CART_WIDTH*CART_WIDTH+CART_HEIGHT*CART_HEIGHT)/12.0,
        M*(CART_LENGTH*CART_LENGTH+CART_WIDTH*CART_WIDTH)/12.0,
        M*(CART_LENGTH*CART_LENGTH+CART_HEIGHT*CART_HEIGHT)/12.0]
    maxima = {}
    minimum_spring = minimum_floor = minimum_cart = minimum_rail = math.inf
    minimum_tension = math.inf
    for row, ref in zip(rows,reference):
        t = row["time"]
        for name,expected in parameters.items():
            require_close(row[name],expected,1e-11,f"{CASE_PREFIX}: independent definition {name}")
        for name,expected in (("cartBody.r_CM",[0.0,0.0,0.0]),("rod.r",[0.0,-L,0.0]),
            ("cartGuide.n",[1.0,0.0,0.0]),("hinge.n",[0.0,0.0,1.0])):
            compare_vector(maxima,"componentParameterResidual",vector(row,name),expected,1e-12,t)
        for i in range(3):
            for j in range(3):
                require_close(row[f"cartBody.I[{i+1},{j+1}]"],inertia[i] if i==j else 0.0,
                    1e-12,"cart density-derived inertia tensor")
                require_close(row[f"cartBody.frame_a.R.T[{i+1},{j+1}]"],1.0 if i==j else 0.0,
                    1e-11,"cart orientation fixed by horizontal guide")

        x,v,theta,omega = (row[n] for n in ("cartDisplacement","cartSpeed","pendulumAngle","pendulumSpeed"))
        a,alpha = row["cartAcceleration"],row["pendulumAcceleration"]
        s,c = math.sin(theta),math.cos(theta)
        ref_a,ref_alpha = nonlinear_accelerations(ref[0],ref[2],ref[3])
        for name,expected,tolerance in (("cartDisplacement",ref[0],2e-6),("cartSpeed",ref[1],1e-5),
            ("pendulumAngle",ref[2],3e-6),("pendulumSpeed",ref[3],1e-5),
            ("cartAcceleration",ref_a,5e-5),("pendulumAcceleration",ref_alpha,1e-4),
            ("springImpulse",ref[4],1e-5)):
            track(maxima,name+"ReferenceError",row[name],expected,tolerance,t)
        for alias,component in (("cartDisplacement","cartGuide.s"),("cartSpeed","cartGuide.v"),
            ("cartAcceleration","cartGuide.a"),("pendulumAngle","hinge.phi"),
            ("pendulumSpeed","hinge.w"),("pendulumAcceleration","hinge.a")):
            require_close(row[alias],row[component],1e-11,"native joint alias "+alias)

        cart,pivot,bob_pos = [x,CART_Y,0.0],[x,PIVOT_Y,0.0],[x+L*s,PIVOT_Y-L*c,0.0]
        cart_v,bob_v = [v,0.0,0.0],[v+L*c*omega,L*s*omega,0.0]
        bob_a = [a+L*c*alpha-L*s*omega*omega,L*s*alpha+L*c*omega*omega,0.0]
        for name,expected in (("cartPosition",cart),("pivotPosition",pivot),("bobPosition",bob_pos),
            ("cartBody.frame_a.r_0",cart),("bob.frame_a.r_0",bob_pos),("rod.frame_a.r_0",pivot),
            ("rod.frame_b.r_0",bob_pos),("cartGuide.frame_a.r_0",[0.0,CART_Y,0.0]),
            ("cartGuide.frame_b.r_0",cart),("hinge.frame_a.r_0",pivot)):
            compare_vector(maxima,"nativeGeometryResidual_m",vector(row,name),expected,1e-8,t)
        for name,expected in (("cartVelocity",cart_v),("cartBody.v_0",cart_v),
            ("bobVelocity",bob_v),("bob.v_0",bob_v)):
            compare_vector(maxima,"nativeVelocityResidual_m_s",vector(row,name),expected,1e-8,t)
        for name,expected in (("bobAcceleration",bob_a),("bob.a_0",bob_a),("cartBody.a_0",[a,0.0,0.0])):
            compare_vector(maxima,"nativeAccelerationResidual_m_s2",vector(row,name),expected,1e-7,t)
        for name in ("cartAngularVelocity","cartBody.body.w_a","cartBody.body.z_a"):
            compare_vector(maxima,"cartRotationResidual",vector(row,name),[0.0]*3,1e-10,t)
        rotation = [[c,s,0.0],[-s,c,0.0],[0.0,0.0,1.0]]
        for i in range(3):
            for j in range(3):
                track(maxima,"nativeRodRotationResidual",row[f"rod.frame_a.R.T[{i+1},{j+1}]"],
                    rotation[i][j],1e-8,t)
        com = [(M*cart[j]+m*bob_pos[j])/(M+m) for j in range(3)]
        compare_vector(maxima,"centerOfMassResidual_m",vector(row,"centerOfMass"),com,1e-9,t)

        # Raw connector forces are resolved independently using the observed
        # angle. Monitors are checked against these values, not used as oracles.
        bob_f = to_world(vector(row,"bob.frame_a.f"),theta)
        cart_pendulum_f = negative(vector(row,"hinge.frame_a.f"))
        rail_f = negative(vector(row,"cartGuide.frame_b.f"))
        rail_t = negative(vector(row,"cartGuide.frame_b.t"))
        spring_f = negative(vector(row,"wallSpring.frame_b.f"))
        for name,actual in (("rodForceOnBob",bob_f),("pendulumForceOnCart",cart_pendulum_f),
            ("railReaction",rail_f),("railTorque",rail_t),("springForceOnCart",spring_f)):
            compare_vector(maxima,"forceTorqueAliasResidual",vector(row,name),actual,1e-9,t)
        compare_vector(maxima,"springForceResidual_N",spring_f,[-k*x,0.0,0.0],1e-7,t)
        compare_vector(maxima,"springActionReactionResidual_N",vector(row,"wallSpring.frame_a.f"),spring_f,1e-7,t)
        compare_vector(maxima,"pendulumActionReactionResidual_N",cart_pendulum_f,negative(bob_f),1e-7,t)
        compare_vector(maxima,"hingeForceTransmissionResidual_N",to_world(vector(row,"hinge.frame_b.f"),theta),
            negative(vector(row,"hinge.frame_a.f")),1e-7,t)
        for j in range(3):
            track(maxima,"bobNewtonResidual_N",bob_f[j]-(m*g if j==1 else 0.0),m*bob_a[j],1e-7,t)
            cart_net = rail_f[j]+spring_f[j]+cart_pendulum_f[j]-(M*g if j==1 else 0.0)
            track(maxima,"cartNewtonResidual_N",cart_net,M*a if j==0 else 0.0,1e-7,t)
            expected_rail = (M+m)*g+m*bob_a[1] if j==1 else 0.0
            track(maxima,"railReactionResidual_N",rail_f[j],expected_rail,1e-7,t)
        tension = m*(g*c-a*s+L*omega*omega)
        track(maxima,"rodTensionResidual_N",row["rodTension"],tension,1e-7,t)
        compare_vector(maxima,"radialRodForceResidual_N",bob_f,[-tension*s,tension*c,0.0],1e-7,t)

        # Independent angular balance for the massless rod and nonrotating cart.
        rod_fa,rod_fb = vector(row,"rod.frame_a.f"),vector(row,"rod.frame_b.f")
        rod_ta,rod_tb = vector(row,"rod.frame_a.t"),vector(row,"rod.frame_b.t")
        rod_moment = cross([0.0,-L,0.0],rod_fb)
        for j in range(3):
            track(maxima,"masslessRodForceResidual_N",rod_fa[j]+rod_fb[j],0.0,1e-7,t)
            track(maxima,"masslessRodTorqueResidual_N_m",rod_ta[j]+rod_tb[j]+rod_moment[j],0.0,1e-7,t)
        compare_vector(maxima,"pointBobTorqueResidual_N_m",vector(row,"bob.frame_a.t"),[0.0]*3,1e-9,t)
        track(maxima,"freeHingeTorqueResidual_N_m",row["hinge.tau"],0.0,1e-10,t)
        track(maxima,"freeHingeTorqueResidual_N_m",row["hinge.frame_b.t[3]"],0.0,1e-10,t)
        pendulum_moment = cross([0.0,-CART_HEIGHT/2.0,0.0],cart_pendulum_f)
        spring_moment = cross([-CART_LENGTH/2.0,0.0,0.0],spring_f)
        hinge_t = negative(vector(row,"hinge.frame_a.t"))
        for j in range(3):
            track(maxima,"cartEulerResidual_N_m",rail_t[j]+pendulum_moment[j]+spring_moment[j]+hinge_t[j],0.0,1e-7,t)
        compare_vector(maxima,"cartBodyTorqueResidual_N_m",vector(row,"cartBody.frame_a.t"),[0.0]*3,1e-9,t)

        # Nonlinear Lagrange residuals and external momentum balance are
        # independent of the above connector balances and reference integrator.
        momentum_rate = (M+m)*a+m*L*(c*alpha-s*omega*omega)
        track(maxima,"horizontalEquationResidual_N",momentum_rate+k*x,0.0,1e-7,t)
        track(maxima,"angularEquationResidual_N_m",m*L*c*a+m*L*L*alpha+m*g*L*s,0.0,1e-7,t)
        track(maxima,"externalMomentumRateResidual_N",momentum_rate,spring_f[0],1e-7,t)
        momentum = M*cart_v[0]+m*bob_v[0]
        track(maxima,"momentumMonitorResidual_N_s",row["horizontalMomentum"],momentum,1e-9,t)
        track(maxima,"externalImpulseBalanceResidual_N_s",momentum,row["springImpulse"],2e-6,t)

        anchor = [-CART_LENGTH/2.0-FREE_LENGTH,CART_Y,0.0]
        attachment = [x-CART_LENGTH/2.0,CART_Y,0.0]
        for name,expected in (("springAnchorPosition",anchor),("wallSpring.frame_a.r_0",anchor),
            ("springCartPosition",attachment),("wallSpring.frame_b.r_0",attachment)):
            compare_vector(maxima,"springAttachmentResidual_m",vector(row,name),expected,1e-8,t)
        for name,expected in (("springLength",FREE_LENGTH+x),("wallSpring.length",FREE_LENGTH+x),
            ("springExtension",x),("springForce",k*x),("wallSpring.f",k*x)):
            track(maxima,"springGeometryConstitutiveResidual",row[name],expected,1e-7,t)
        kinetic = (M*dot(cart_v,cart_v)+m*dot(bob_v,bob_v))/2.0
        gravitational = g*(M*cart[1]+m*bob_pos[1])
        elastic = k*x*x/2.0
        energy = kinetic+gravitational+elastic
        for name,expected in (("kineticEnergy",kinetic),("gravitationalEnergy",gravitational),
            ("elasticEnergy",elastic),("totalEnergy",energy)):
            track(maxima,"energyMonitorResidual_J",row[name],expected,1e-8,t)
        track(maxima,"energyDrift_J",energy,INITIAL_ENERGY,5e-5,t)
        rod_power = dot(bob_f,bob_v)+dot(cart_pendulum_f,cart_v)
        guide_power = dot(rail_f,cart_v)
        spring_power = dot(spring_f,cart_v)
        for name,actual,expected in (("rodPower",rod_power,0.0),("guidePower",guide_power,0.0),
            ("springPower",spring_power,-k*x*v)):
            track(maxima,"powerMonitorResidual_W",row[name],actual,1e-8,t)
            track(maxima,"constraintSpringPowerResidual_W",actual,expected,1e-7,t)
        mechanical_power = M*dot([a,0.0,0.0],cart_v)+m*dot(bob_a,bob_v)+m*g*bob_v[1]+k*x*v
        track(maxima,"totalEnergyRateResidual_W",mechanical_power,0.0,1e-7,t)

        spring_length = FREE_LENGTH+x
        floor_clearance = bob_pos[1]-BOB_DIAMETER/2.0
        cart_clearance = cart[1]-CART_HEIGHT/2.0-(bob_pos[1]+BOB_DIAMETER/2.0)
        rail_clearance = min(x-CART_LENGTH/2.0+1.35,1.12-x-CART_LENGTH/2.0)
        minimum_spring = min(minimum_spring,spring_length)
        minimum_floor,minimum_cart = min(minimum_floor,floor_clearance),min(minimum_cart,cart_clearance)
        minimum_rail,minimum_tension = min(minimum_rail,rail_clearance),min(minimum_tension,tension)
        if spring_length<=0.05 or min(floor_clearance,cart_clearance,rail_clearance)<=0.0:
            raise AssertionError(f"{CASE_PREFIX}: invalid nominal geometry at {t:g} s")

    first = rows[0]
    initial_a,initial_alpha = nonlinear_accelerations(0.0,THETA0,0.0)
    for name,value in (("cartDisplacement",0.0),("cartSpeed",0.0),("pendulumAngle",THETA0),
        ("pendulumSpeed",0.0),("springImpulse",0.0),("springForce",0.0)):
        require_close(first[name],value,1e-10,"independent release condition "+name)
    require_close(first["cartAcceleration"],initial_a,1e-7,"independent initial cart acceleration")
    require_close(first["pendulumAcceleration"],initial_alpha,1e-7,"independent initial pendulum acceleration")
    require_close(first["pendulumForceOnCart[1]"],M*initial_a,1e-7,"pendulum initially accelerates the free cart")
    x_range = [min(r["cartDisplacement"] for r in rows),max(r["cartDisplacement"] for r in rows)]
    theta_range = [min(r["pendulumAngle"] for r in rows),max(r["pendulumAngle"] for r in rows)]
    cart_reversals = sum(a["cartSpeed"]*b["cartSpeed"]<0.0 for a,b in zip(rows,rows[1:]))
    pendulum_reversals = sum(a["pendulumSpeed"]*b["pendulumSpeed"]<0.0 for a,b in zip(rows,rows[1:]))
    momentum_range = [min(r["horizontalMomentum"] for r in rows),max(r["horizontalMomentum"] for r in rows)]
    if x_range[1]-x_range[0]<0.2 or theta_range[1]-theta_range[0]<0.7 or cart_reversals<3 or pendulum_reversals<3:
        raise AssertionError("The nominal run must visibly exhibit coupled translational and rotational motion")
    if momentum_range[1]-momentum_range[0]<0.1:
        raise AssertionError("The wall spring must produce observable external horizontal impulse")
    return {"passed":True,"model":MODEL_NAME,"samples":len(rows),"startTime":rows[0]["time"],
        "stopTime":rows[-1]["time"],"cartTravelRange_m":x_range,"pendulumAngleRange_rad":theta_range,
        "horizontalMomentumRange_N_s":momentum_range,"cartVelocityReversals":cart_reversals,
        "pendulumVelocityReversals":pendulum_reversals,"minimumSpringLength_m":minimum_spring,
        "minimumBobFloorClearance_m":minimum_floor,"minimumBobCartVerticalClearance_m":minimum_cart,
        "minimumCarriageRailClearance_m":minimum_rail,"minimumRodTension_N":minimum_tension,
        "initialCartAcceleration_m_s2":initial_a,"initialPendulumAcceleration_rad_s2":initial_alpha,
        "cartInertiaDiagonal_kg_m2":inertia,"bobRotationalInertia_kg_m2":0.0,
        "reference":reference_report,"maxErrors":maxima,
        "scope":"One undamped, planar, bilateral-guide composition with a massless rigid rod and ideal point bob; no contact, friction or deformation.",
        "momentumAccounting":"Horizontal momentum is not conserved. Its rate is the native spring force and its change equals the native force integral."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-only",action="store_true",
        help="Check the independent reference without claiming native Modelica verification")
    args = parser.parse_args()
    if args.reference_only:
        times = [i*0.005 for i in range(MINIMUM_SAMPLES)]
        states, report = checked_reference(times)
        report.update({"scope":"Independent numerical reference only; no native Modelica run verified",
            "cartTravelRange_m":[min(s[0] for s in states),max(s[0] for s in states)],
            "pendulumAngleRange_rad":[min(s[2] for s in states),max(s[2] for s in states)],
            "initialAccelerations":nonlinear_accelerations(0.0,THETA0,0.0),
            "at_0_4_s":states[80]})
        print(json.dumps(report,indent=2))
    else:
        print(json.dumps(verify_cart(),indent=2))


if __name__ == "__main__":
    main()
