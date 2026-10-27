"""Camera/model subprocess; only launched by an explicit dashboard action."""
import argparse
import sys
import traceback
from .bridge import DashboardBridge


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--frame-path', required=True)
    args, remaining = parser.parse_known_args()
    bridge = DashboardBridge(args.frame_path)
    try:
        sys.argv = ['live_smart_bin.py', *remaining]
        import live_smart_bin
        live_smart_bin.main(bridge=bridge)
    except Exception as error:
        bridge.emit('error', message=str(error))
        traceback.print_exc(file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
