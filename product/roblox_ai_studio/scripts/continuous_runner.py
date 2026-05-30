"""Continuous autonomous backend runner for Roblox AI Studio.

Runs queued build loops continuously. Explicitly relies on global provider
fallback chain and does NOT override model or provider to force
cliproxyapi + gpt-5.5, per task constraints.
"""

import time
import argparse
import logging
from pathlib import Path

from product.roblox_ai_studio.build_loop import run_build_loop_tick, load_build_mission, BuildLoopStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_active_missions(projects_dir: Path) -> list[Path]:
    """Find all projects that have a running build mission."""
    active = []
    if not projects_dir.exists():
        return active
        
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
            
        mission_file = project_dir / "build_mission.json"
        if mission_file.exists():
            try:
                mission = load_build_mission(project_dir)
                if mission.loop.status == BuildLoopStatus.RUNNING:
                    active.append(project_dir)
            except Exception as e:
                logging.error(f"Failed to read mission in {project_dir}: {e}")
                
    return active

def run_continuous_batch(projects_dir: Path, ticks: int = 1, delay: float = 2.0):
    """Run batch ticks across all active missions."""
    logging.info(f"Starting continuous batch runner on {projects_dir} for {ticks} ticks.")
    
    for iteration in range(ticks):
        active_missions = get_active_missions(projects_dir)
        if not active_missions:
            logging.info("No active running missions found.")
            break
            
        logging.info(f"Tick {iteration + 1}/{ticks}: processing {len(active_missions)} active missions.")
        for project_dir in active_missions:
            logging.info(f"Running tick for {project_dir.name}...")
            try:
                # We use run_build_loop_tick which currently falls back to the safe determinism
                # or calls the hermes CLI *without* overriding the provider. The underlying
                # _run_hermes_agent uses existing global fallbacks. 
                job = run_build_loop_tick(project_dir)
                logging.info(f"Completed phase {job.phase} with status {job.status}.")
            except Exception as e:
                logging.error(f"Error ticking {project_dir.name}: {e}")
                
        if iteration < ticks - 1:
            time.sleep(delay)
            
    logging.info("Continuous batch run finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Roblox AI Studio continuous build batch runner.")
    parser.add_argument(
        "--projects-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "generated_projects",
        help="Path to generated projects directory",
    )
    parser.add_argument("--ticks", type=int, default=1, help="Number of loop iterations to run")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between ticks")
    
    args = parser.parse_args()
    run_continuous_batch(args.projects_dir, args.ticks, args.delay)
