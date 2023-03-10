# Copyright (c) 2022 Boston Dynamics, Inc.  All rights reserved.
#
# Downloading, reproducing, distributing or otherwise using the SDK Software
# is subject to the terms and conditions of the Boston Dynamics Software
# Development Kit License (20191101-BDSDK-SL).

"""Tutorial to show how to use Spot's arm.
"""
from __future__ import print_function

import argparse
import sys
import time

import bosdyn.api.gripper_command_pb2
import bosdyn.client
import bosdyn.client.lease
import bosdyn.client.util
from bosdyn.api import arm_command_pb2, robot_command_pb2, synchronized_command_pb2, trajectory_pb2
from bosdyn.client import math_helpers
from bosdyn.client.frame_helpers import GRAV_ALIGNED_BODY_FRAME_NAME
from bosdyn.client.robot_command import RobotCommandBuilder, RobotCommandClient, blocking_stand
from bosdyn.util import seconds_to_duration


def pour_grinds(config):

    # See hello_spot.py for an explanation of these lines.
    bosdyn.client.util.setup_logging(config.verbose)

    sdk = bosdyn.client.create_standard_sdk('ArmTrajectory')
    robot = sdk.create_robot(config.hostname)
    bosdyn.client.util.authenticate(robot)
    robot.time_sync.wait_for_sync()

    assert robot.has_arm(), "Robot requires an arm to run this example."

    # Verify the robot is not estopped and that an external application has registered and holds
    # an estop endpoint.
    assert not robot.is_estopped(), "Robot is estopped. Please use an external E-Stop client, " \
                                    "such as the estop SDK example, to configure E-Stop."

    lease_client = robot.ensure_client(bosdyn.client.lease.LeaseClient.default_service_name)
    with bosdyn.client.lease.LeaseKeepAlive(lease_client, must_acquire=True, return_at_exit=True):
        # Now, we are ready to power on the robot. This call will block until the power
        # is on. Commands would fail if this did not happen. We can also check that the robot is
        # powered at any point.
        robot.logger.info("Powering on robot... This may take a several seconds.")
        robot.power_on(timeout_sec=20)
        assert robot.is_powered_on(), "Robot power on failed."
        robot.logger.info("Robot powered on.")

        # Tell the robot to stand up. The command service is used to issue commands to a robot.
        # The set of valid commands for a robot depends on hardware configuration. See
        # RobotCommandBuilder for more detailed examples on command building. The robot
        # command service requires timesync between the robot and the client.
        robot.logger.info("Commanding robot to stand...")
        command_client = robot.ensure_client(RobotCommandClient.default_service_name)
        blocking_stand(command_client, timeout_sec=10)
        robot.logger.info("Robot standing.")

        # Move the arm along a simple trajectory.

        holding_quat = math_helpers.Quat.from_roll(1.57)
        full_pour_quat = math_helpers.Quat.from_roll(-1)
        partial_pour_quat = math_helpers.Quat.from_roll(-0.9)

        # Use the same rotation as the robot's body.
        rotation = math_helpers.Quat()

        #x,y,z,rot,time
        # cmd_poses = [
        # [0.75, 0, 0.25, holding_quat, 0],
        # [0.75, 0, 0.38, holding_quat, 3.0], #Raise hand up
        # [1.00, -0.07, 0.38, holding_quat, 6.0], #Move hand over coffee machine
        # [1.00, -0.07, 0.38, holding_quat, 7.0], #pause
        # [1.00, -0.07, 0.38, full_pour_quat, 10.0], #Pour grinds
        # [1.00, -0.07, 0.38, partial_pour_quat, 10.1], #shakey
        # [1.00, -0.07, 0.38, full_pour_quat, 10.2], #shakey
        # [1.00, -0.07, 0.38, partial_pour_quat, 10.3], #shakey
        # [1.00, -0.07, 0.38, full_pour_quat, 10.4], #shakey
        # [1.00, -0.07, 0.38, full_pour_quat, 12], #hold
        # [1.00, -0.07, 0.38, holding_quat, 14.0], #right cup
        # [0.75, 0, 0.38, holding_quat, 16.0], #Retract x
        # [0.75, 0, 0.25, holding_quat, 18.0], #retract z
        # ]


        cmd_poses = [
        [0.75, 0, 0.25, holding_quat, 0],
        [0.75, 0, 0.38, holding_quat, 1.0], #ericpour
        [0.75, 0, 0.38, holding_quat, 3.0], #Raise hand up
        [1.00, -0.06, 0.38, holding_quat, 6.0], #Move hand over coffee machine
        [1.00, -0.06, 0.38, holding_quat, 7.0], #pause
        [1.00, -0.06, 0.38, full_pour_quat, 10.0], #Pour grinds
        [1.00, -0.06, 0.38, partial_pour_quat, 10.1], #shakey
        [1.00, -0.06, 0.38, full_pour_quat, 10.2], #shakey
        [1.00, -0.06, 0.38, partial_pour_quat, 10.3], #shakey
        [1.00, -0.06, 0.38, full_pour_quat, 10.4], #shakey
        [1.00, -0.06, 0.38, full_pour_quat, 12], #hold
        [1.00, -0.06, 0.38, holding_quat, 14.0], #right cup
        [0.75, 0, 0.38, holding_quat, 16.0], #Retract x
        [0.75, 0, 0.25, holding_quat, 18.0], #retract z
        ]

        hand_poses = []
        for cmd_pose in cmd_poses:
            # Build the points in the trajectory.
            hand_poses.append(math_helpers.SE3Pose(x=cmd_pose[0], y=cmd_pose[1], z=cmd_pose[2], rot=cmd_pose[3]))

        traj_points = []
        for idx, hand_pose in enumerate(hand_poses):
        # Build the points by combining the pose and times into protos.
            traj_point = trajectory_pb2.SE3TrajectoryPoint(
                pose=hand_pose.to_proto(), time_since_reference=seconds_to_duration(cmd_poses[idx][-1]))
            traj_points.append(traj_point)


        # Build the trajectory proto by combining the points.
        hand_traj = trajectory_pb2.SE3Trajectory(points=traj_points)

        # Build the command by taking the trajectory and specifying the frame it is expressed
        # in.
        #
        # In this case, we want to specify the trajectory in the body's frame, so we set the
        # root frame name to the flat body frame.
        arm_cartesian_command = arm_command_pb2.ArmCartesianCommand.Request(
            pose_trajectory_in_task=hand_traj, root_frame_name=GRAV_ALIGNED_BODY_FRAME_NAME)

        # Pack everything up in protos.
        arm_command = arm_command_pb2.ArmCommand.Request(
            arm_cartesian_command=arm_cartesian_command)

        synchronized_command = synchronized_command_pb2.SynchronizedCommand.Request(
            arm_command=arm_command)

        robot_command = robot_command_pb2.RobotCommand(synchronized_command=synchronized_command)

        # Keep the gripper closed the whole time.
        robot_command = RobotCommandBuilder.claw_gripper_open_fraction_command(
            0, build_on_command=robot_command)

        robot.logger.info("Sending trajectory command...")

        # Send the trajectory to the robot.
        cmd_id = command_client.robot_command(robot_command)

        # Wait until the arm arrives at the goal.
        while True:
            feedback_resp = command_client.robot_command_feedback(cmd_id)
            robot.logger.info('Distance to final point: ' + '{:.2f} meters'.format(
                feedback_resp.feedback.synchronized_feedback.arm_command_feedback.
                arm_cartesian_feedback.measured_pos_distance_to_goal) + ', {:.2f} radians'.format(
                    feedback_resp.feedback.synchronized_feedback.arm_command_feedback.
                    arm_cartesian_feedback.measured_rot_distance_to_goal))

            if feedback_resp.feedback.synchronized_feedback.arm_command_feedback.arm_cartesian_feedback.status == arm_command_pb2.ArmCartesianCommand.Feedback.STATUS_TRAJECTORY_COMPLETE:
                robot.logger.info('Move complete.')
                break
            time.sleep(0.1)

        # Power the robot off. By specifying "cut_immediately=False", a safe power off command
        # is issued to the robot. This will attempt to sit the robot before powering off.
        robot.power_off(cut_immediately=False, timeout_sec=20)
        assert not robot.is_powered_on(), "Robot power off failed."
        robot.logger.info("Robot safely powered off.")


def close_lid_integrated(robot, command_client):
    neutral_quat = math_helpers.Quat.from_roll(0)
    hooking_quat = math_helpers.Quat.from_yaw(1.57)

    cmd_poses = [[
        [0.75, 0, 0.25, neutral_quat, 0],
        [0.75, 0, 0.38, neutral_quat, 1.0],  # ericpour
        [0.75, 0, 0.38, neutral_quat, 2.0],  # Raise hand up
        [1.00, 0, 0.38, neutral_quat, 3.0],  # extend arm
        [0.35, .75, 0.38, hooking_quat, 7.0] # Move hand over coffee machine
        ],
        [[0.35, .75, 0.38, hooking_quat, 0],
        [0.75, 0, 0.38, neutral_quat, 1.0],
        [0.75, 0, 0.25, neutral_quat, 2]]
    ]

    for cmd_pose in cmd_poses:
        execute_trajectory_from_poses(robot, command_client, cmd_pose)



def pour_grinds_integrated(robot, command_client):
    # Move the arm along a simple trajectory.

    holding_quat = math_helpers.Quat.from_roll(1.57)
    full_pour_quat = math_helpers.Quat.from_roll(-1)
    partial_pour_quat = math_helpers.Quat.from_roll(-0.9)

    shake_poses = [
    #[0.75, 0, 0.25, holding_quat, 0],
    #[0.75, 0, 0.38, holding_quat, 1.0], #ericpour
    [0.75, 0, 0.38, holding_quat, 3.0], #Raise hand up
    [1.00, -0.06, 0.38, holding_quat, 6.0], #Move hand over coffee machine
    [1.00, -0.06, 0.38, holding_quat, 7.0], #pause
    [1.00, -0.06, 0.38, full_pour_quat, 10.0], #Pour grinds
    [1.00, -0.06, 0.38, partial_pour_quat, 10.1], #shakey
    [1.00, -0.06, 0.38, full_pour_quat, 10.2], #shakey
    [1.00, -0.06, 0.38, partial_pour_quat, 10.3], #shakey
    [1.00, -0.06, 0.38, full_pour_quat, 10.4], #shakey
    ]
    retract_poses = [
    [1.00, -0.06, 0.38, full_pour_quat, 0], #hold
    [1.00, -0.06, 0.38, holding_quat, 1], #right cup
    [0.75, 0, 0.38, holding_quat, 2], #Retract x
    [0.75, 0, 0.25, holding_quat, 3], #retract z
    ]

    execute_trajectory_from_poses(robot, command_client, shake_poses)
    execute_trajectory_from_poses(robot, command_client, retract_poses)



def execute_trajectory_from_poses(robot, command_client, cmd_poses):
    robot.time_sync.wait_for_sync()

    assert robot.has_arm(), "Robot requires an arm to run this example."

    # Verify the robot is not estopped and that an external application has registered and holds
    # an estop endpoint.
    assert not robot.is_estopped(), "Robot is estopped. Please use an external E-Stop client, " \
                                    "such as the estop SDK example, to configure E-Stop."


    # Use the same rotation as the robot's body.
    rotation = math_helpers.Quat()

    #x,y,z,rot,time
    # cmd_poses = [
    # [0.75, 0, 0.25, holding_quat, 0],
    # [0.75, 0, 0.38, holding_quat, 3.0], #Raise hand up
    # [1.00, -0.07, 0.38, holding_quat, 6.0], #Move hand over coffee machine
    # [1.00, -0.07, 0.38, holding_quat, 7.0], #pause
    # [1.00, -0.07, 0.38, full_pour_quat, 10.0], #Pour grinds
    # [1.00, -0.07, 0.38, partial_pour_quat, 10.1], #shakey
    # [1.00, -0.07, 0.38, full_pour_quat, 10.2], #shakey
    # [1.00, -0.07, 0.38, partial_pour_quat, 10.3], #shakey
    # [1.00, -0.07, 0.38, full_pour_quat, 10.4], #shakey
    # [1.00, -0.07, 0.38, full_pour_quat, 12], #hold
    # [1.00, -0.07, 0.38, holding_quat, 14.0], #right cup
    # [0.75, 0, 0.38, holding_quat, 16.0], #Retract x
    # [0.75, 0, 0.25, holding_quat, 18.0], #retract z
    # ]


    hand_poses = []
    for cmd_pose in cmd_poses:
        # Build the points in the trajectory.
        hand_poses.append(math_helpers.SE3Pose(x=cmd_pose[0], y=cmd_pose[1], z=cmd_pose[2], rot=cmd_pose[3]))

    traj_points = []
    for idx, hand_pose in enumerate(hand_poses):
    # Build the points by combining the pose and times into protos.
        traj_point = trajectory_pb2.SE3TrajectoryPoint(
            pose=hand_pose.to_proto(), time_since_reference=seconds_to_duration(cmd_poses[idx][-1]))
        traj_points.append(traj_point)


    # Build the trajectory proto by combining the points.
    hand_traj = trajectory_pb2.SE3Trajectory(points=traj_points)


    # Build the command by taking the trajectory and specifying the frame it is expressed
    # in.
    #
    # In this case, we want to specify the trajectory in the body's frame, so we set the
    # root frame name to the flat body frame.
    arm_cartesian_command = arm_command_pb2.ArmCartesianCommand.Request(
        pose_trajectory_in_task=hand_traj, root_frame_name=GRAV_ALIGNED_BODY_FRAME_NAME)

    # Pack everything up in protos.
    arm_command = arm_command_pb2.ArmCommand.Request(
        arm_cartesian_command=arm_cartesian_command)

    synchronized_command = synchronized_command_pb2.SynchronizedCommand.Request(
        arm_command=arm_command)

    robot_command = robot_command_pb2.RobotCommand(synchronized_command=synchronized_command)

    # Keep the gripper closed the whole time.
    robot_command = RobotCommandBuilder.claw_gripper_open_fraction_command(
        0, build_on_command=robot_command)

    robot.logger.info("Sending trajectory command...")

    # Send the trajectory to the robot.
    cmd_id = command_client.robot_command(robot_command)

    # Wait until the arm arrives at the goal.
    while True:
        feedback_resp = command_client.robot_command_feedback(cmd_id)
        print('Distance to final point: ' + '{:.2f} meters'.format(
            feedback_resp.feedback.synchronized_feedback.arm_command_feedback.
            arm_cartesian_feedback.measured_pos_distance_to_goal) + ', {:.2f} radians'.format(
                feedback_resp.feedback.synchronized_feedback.arm_command_feedback.
                arm_cartesian_feedback.measured_rot_distance_to_goal))

        if feedback_resp.feedback.synchronized_feedback.arm_command_feedback.arm_cartesian_feedback.status == arm_command_pb2.ArmCartesianCommand.Feedback.STATUS_TRAJECTORY_COMPLETE:
            print('Move complete.')
            break
        time.sleep(0.1)





def main(argv):
    """Command line interface."""
    parser = argparse.ArgumentParser()
    bosdyn.client.util.add_base_arguments(parser)
    options = parser.parse_args(argv)
    try:
        pour_grinds(options)
        return True
    except Exception as exc:  # pylint: disable=broad-except
        logger = bosdyn.client.util.get_logger()
        logger.exception("Threw an exception")
        return False


if __name__ == '__main__':
    if not main(sys.argv[1:]):
        sys.exit(1)
