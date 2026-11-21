"""Run: python3 -m unittest discover -s tests -v   (no ROS / robot needed)"""
import os, sys, time, unittest, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from smoke_response import Evacuator, FakeLed, FakeNav, RED, BLUE, GREEN

logging.disable(logging.CRITICAL)


def wait(cond, t=3.0):
    t0 = time.time()
    while time.time() - t0 < t:
        if cond():
            return True
        time.sleep(0.02)
    return False


class EvacTest(unittest.TestCase):
    def make(self, ok=True, delay=0.5):
        led, nav = FakeLed(quiet=True), FakeNav(ok=ok, delay=delay)
        return Evacuator(nav, led, safe=(1.2, 1.2, 0.0), retries=1, period=0.05), led, nav

    def test_alarm_siren_alternates_then_green_on_arrival(self):
        ev, led, nav = self.make(ok=True, delay=0.5)
        self.assertTrue(ev.alarm())
        self.assertTrue(wait(lambda: ev.state == ev.ARRIVED))
        fills = [c for k, c in led.calls if k == 'fill']
        colours = [c for c in fills if c in (RED, BLUE)]
        self.assertIn(RED, colours); self.assertIn(BLUE, colours)
        self.assertTrue(all(colours[i] != colours[i + 1] for i in range(len(colours) - 1)), 'must strictly alternate')
        self.assertEqual(fills[-1], GREEN)
        n = len(led.calls); time.sleep(0.3)
        self.assertEqual(len(led.calls), n, 'siren must be off after arrival')

    def test_second_alarm_ignored_while_busy(self):
        ev, led, nav = self.make(delay=0.5)
        self.assertTrue(ev.alarm()); self.assertFalse(ev.alarm())
        wait(lambda: ev.state == ev.ARRIVED); self.assertFalse(ev.alarm())

    def test_failure_keeps_siren_on(self):
        ev, led, nav = self.make(ok=False, delay=0.05)
        ev.alarm(); self.assertTrue(wait(lambda: ev.state == ev.FAILED, 5))
        n = len(led.calls); time.sleep(0.3)
        self.assertGreater(len(led.calls), n, 'siren should keep blinking on failure')
        ev.reset(); self.assertEqual(ev.state, ev.IDLE)

    def test_reset_cancels_and_clears(self):
        ev, led, nav = self.make(delay=1.0)
        ev.alarm(); time.sleep(0.2); ev.reset()
        self.assertTrue(nav.cancelled); self.assertEqual(led.calls[-1][0], 'clear'); self.assertEqual(ev.state, ev.IDLE)
        time.sleep(1.3); self.assertEqual(ev.state, ev.IDLE, 'finished goto must not resurrect state after reset')
        self.assertTrue(ev.alarm(), 'can alarm again after reset')
        ev.reset()


if __name__ == '__main__':
    unittest.main()
