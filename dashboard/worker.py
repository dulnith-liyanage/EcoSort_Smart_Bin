"""Single camera/model owner, started by the dashboard or its boot service."""
import argparse
import sys
import traceback
from .bridge import DashboardBridge


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--frame-path', required=True)
    parser.add_argument('--auto-sort', action='store_true')
    args, remaining = parser.parse_known_args()
    bridge = DashboardBridge(args.frame_path, auto_sort=args.auto_sort)
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
