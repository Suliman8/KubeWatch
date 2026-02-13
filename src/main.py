"""
KubeWatch - Main Entry Point
Kubernetes Monitoring & Observability Platform
Created by SULIMAN KHAN
"""

import sys
import argparse
from colorama import Fore, Style, init

init(autoreset=True)

BANNER = f"""
{Fore.CYAN}╔═══════════════════════════════════════════════════╗
║                                                   ║
║   {Fore.WHITE}██╗  ██╗██╗   ██╗██████╗ ███████╗{Fore.CYAN}                ║
║   {Fore.WHITE}██║ ██╔╝██║   ██║██╔══██╗██╔════╝{Fore.CYAN}                ║
║   {Fore.WHITE}█████╔╝ ██║   ██║██████╔╝█████╗  {Fore.CYAN}                ║
║   {Fore.WHITE}██╔═██╗ ██║   ██║██╔══██╗██╔══╝  {Fore.CYAN}                ║
║   {Fore.WHITE}██║  ██╗╚██████╔╝██████╔╝███████╗{Fore.CYAN}                ║
║   {Fore.WHITE}╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝{Fore.CYAN}               ║
║           {Fore.YELLOW}W A T C H{Fore.CYAN}   v1.0.0                    ║
║                                                   ║
║   {Fore.GREEN}Kubernetes Monitoring & Observability{Fore.CYAN}            ║
║   {Fore.WHITE}Created by SULIMAN KHAN{Fore.CYAN}                         ║
║                                                   ║
╚═══════════════════════════════════════════════════╝{Style.RESET_ALL}
"""


def cmd_dashboard(args):
    """Start the web dashboard."""
    from src.dashboard.app import run_dashboard
    print(f"\n  {Fore.GREEN}Starting KubeWatch Dashboard...{Style.RESET_ALL}")
    run_dashboard(host=args.host, port=args.port)


def cmd_monitor(args):
    """Run CLI monitoring (one-shot snapshot)."""
    import json
    from src.collectors.k8s_connector import connect, get_full_snapshot, enrich_snapshot
    from src.collectors.metrics_collector import get_pod_metrics
    from src.alerting.alert_engine import AlertEngine

    print(f"\n  {Fore.CYAN}Connecting to Kubernetes cluster...{Style.RESET_ALL}")
    apis = connect()

    print(f"  {Fore.CYAN}Collecting cluster data...{Style.RESET_ALL}\n")
    snapshot = get_full_snapshot(apis, namespace=args.namespace)
    snapshot = enrich_snapshot(snapshot)

    # Print summary
    pods = snapshot.get("pods", [])
    nodes = snapshot.get("nodes", [])
    deploys = snapshot.get("deployments", [])

    print(f"  {Fore.WHITE}{'='*50}{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}CLUSTER SUMMARY{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}{'='*50}{Style.RESET_ALL}")
    print(f"  Nodes:       {Fore.GREEN}{len(nodes)}{Style.RESET_ALL}")
    print(f"  Pods:        {Fore.GREEN}{len(pods)}{Style.RESET_ALL}")
    running = sum(1 for p in pods if p["status"] == "Running")
    print(f"  Running:     {Fore.GREEN}{running}{Style.RESET_ALL}")
    print(f"  Deployments: {Fore.GREEN}{len(deploys)}{Style.RESET_ALL}")
    total_restarts = sum(p["restart_count"] for p in pods)
    print(f"  Restarts:    {Fore.YELLOW if total_restarts > 0 else Fore.GREEN}{total_restarts}{Style.RESET_ALL}")

    # Alerts
    print(f"\n  {Fore.WHITE}{'='*50}{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}ALERTS{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}{'='*50}{Style.RESET_ALL}")

    alert_engine = AlertEngine()
    pod_metrics = get_pod_metrics(apis, namespace=args.namespace)
    alerts = alert_engine.evaluate(snapshot, pod_metrics)
    alert_engine.print_alerts()

    # Health scores
    print(f"\n  {Fore.WHITE}{'='*50}{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}HEALTH SCORES{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}{'='*50}{Style.RESET_ALL}")

    scores = alert_engine.get_health_scores(snapshot, pod_metrics)
    for name, info in scores.items():
        score = info["score"]
        if score >= 90:
            color = Fore.GREEN
        elif score >= 70:
            color = Fore.YELLOW
        else:
            color = Fore.RED
        print(f"  {info['name']:30s} {color}{score:3d}/100{Style.RESET_ALL}  [{info['replicas']}]")

    if args.json:
        print(f"\n  {Fore.WHITE}{'='*50}{Style.RESET_ALL}")
        print(json.dumps(snapshot, indent=2, default=str))

    print()


def cmd_logs(args):
    """View pod logs."""
    from src.collectors.k8s_connector import connect
    from src.collectors.log_collector import get_pod_logs, get_error_logs

    apis = connect()

    if args.errors:
        print(f"\n  {Fore.CYAN}Scanning for error logs...{Style.RESET_ALL}\n")
        errors = get_error_logs(apis, namespace=args.namespace)
        if not errors:
            print(f"  {Fore.GREEN}No errors found!{Style.RESET_ALL}")
        else:
            for err in errors[:50]:
                print(f"  {Fore.RED}[{err['pod']}]{Style.RESET_ALL} {err['text']}")
    elif args.pod:
        print(f"\n  {Fore.CYAN}Fetching logs for {args.pod}...{Style.RESET_ALL}\n")
        log_data = get_pod_logs(apis, args.pod, namespace=args.namespace, lines=args.lines)
        if log_data.get("error"):
            print(f"  {Fore.RED}Error: {log_data['error']}{Style.RESET_ALL}")
        else:
            for line in log_data["lines"]:
                print(f"  {line}")
    else:
        print(f"  {Fore.YELLOW}Specify --pod <name> or --errors{Style.RESET_ALL}")

    print()


def main():
    print(BANNER)

    parser = argparse.ArgumentParser(
        description="KubeWatch - Kubernetes Monitoring & Observability Platform"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Dashboard command
    dash_parser = subparsers.add_parser("dashboard", help="Start the web dashboard")
    dash_parser.add_argument("--host", default="0.0.0.0", help="Dashboard host (default: 0.0.0.0)")
    dash_parser.add_argument("--port", type=int, default=8080, help="Dashboard port (default: 8080)")

    # Monitor command
    mon_parser = subparsers.add_parser("monitor", help="Run CLI monitoring snapshot")
    mon_parser.add_argument("--namespace", "-n", default="default", help="Namespace to monitor")
    mon_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # Logs command
    log_parser = subparsers.add_parser("logs", help="View pod logs")
    log_parser.add_argument("--pod", "-p", help="Pod name")
    log_parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    log_parser.add_argument("--lines", "-l", type=int, default=100, help="Number of lines")
    log_parser.add_argument("--errors", "-e", action="store_true", help="Show error logs from all pods")

    args = parser.parse_args()

    if args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "monitor":
        cmd_monitor(args)
    elif args.command == "logs":
        cmd_logs(args)
    else:
        parser.print_help()
        print(f"\n  {Fore.CYAN}Examples:{Style.RESET_ALL}")
        print(f"    python -m src.main dashboard          Start the web dashboard")
        print(f"    python -m src.main monitor             CLI cluster snapshot")
        print(f"    python -m src.main monitor --json      Full JSON output")
        print(f"    python -m src.main logs --pod <name>   View pod logs")
        print(f"    python -m src.main logs --errors       Scan for error logs")
        print()


if __name__ == "__main__":
    main()
