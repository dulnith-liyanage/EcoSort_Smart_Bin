"""Motion bounds and velocity checks; no hardware or wall-clock sleeps."""
import math
import unittest
from servo_settings import Calibration,motion_steps


class MotionProfileTests(unittest.TestCase):
    def test_smooth_moves_are_bounded_monotonic_exact_and_speed_limited(self):
        for start,target in [(90,135),(135,90),(125,90),(90,125),(125,160),(160,125),(90,91)]:
            with self.subTest(start=start,target=target):
                steps=list(motion_steps(start,target,.04,True))
                previous=start
                speed=[]
                for angle,delay in steps:
                    self.assertTrue(math.isfinite(angle))
                    self.assertLessEqual(min(start,target),angle)
                    self.assertLessEqual(angle,max(start,target))
                    self.assertGreater(delay,0)
                    self.assertLessEqual(delay,.020000001)
                    self.assertGreaterEqual((angle-previous)*(target-start),0)
                    speed.append(abs(angle-previous)/delay)
                    previous=angle
                self.assertEqual(previous,target)
                self.assertLessEqual(max(speed),25.000001)
                self.assertLess(speed[0],max(speed)/10)
                self.assertLess(speed[-1],max(speed)/10)
                self.assertGreaterEqual(sum(delay for _,delay in steps),abs(target-start)*.04)

    def test_stationary_move_does_not_write(self):
        self.assertEqual(list(motion_steps(125,125,.04,True)),[])

    def test_bad_targets_and_timing_fail_before_any_output(self):
        for args in [(-1,90,.04),(90,181,.04),(90,125,0),(True,90,.04),(90,float('nan'),.04)]:
            with self.subTest(args=args),self.assertRaises(ValueError):
                list(motion_steps(*args,True))
        for value in [None,1,'yes']:
            with self.assertRaises(ValueError):
                Calibration(smooth_motion=value)

    def test_legacy_mode_is_preserved(self):
        self.assertEqual(list(motion_steps(90,92,.04)),[(90,.04),(91,.04),(92,.04)])


if __name__=='__main__':unittest.main()
