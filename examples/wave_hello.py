from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

with ReachyMini() as mini:
    # Wave the antennas
    mini.goto_target(antennas=[0.6, -0.6], duration=0.3)
    mini.goto_target(antennas=[-0.6, 0.6], duration=0.3)
    mini.goto_target(antennas=[0, 0], duration=0.3)

    # Nod hello
    mini.goto_target(
        head=create_head_pose(z=15, degrees=True),
        duration=0.5
    )
    mini.goto_target(
        head=create_head_pose(z=-15, degrees=True),
        duration=0.5
    )
    mini.goto_target(
        head=create_head_pose(z=0, degrees=True),
        duration=0.5
    )