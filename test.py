import subprocess
import os
import sys

# --- Configuration (mimicking GitHub Actions environment/secrets) ---
# In a real scenario, you'd get these from environment variables or a secure configuration system.
DOCKER_USERNAME = os.getenv("DOCKER_USERNAME", "your_docker_username")
DOCKER_PASSWORD = os.getenv("DOCKER_PASSWORD", "your_docker_password") # WARNING: Do not hardcode secrets!

# Define commands as a list of lists, where each inner list is a command and its arguments
# This makes it easier to pass to subprocess.run
workflow_steps = [
    {"name": "Checkout Code (simulated)", "command": ["echo", "Simulating code checkout..."]},
    # Note: 'actions/checkout' is a specific GitHub Action, not a simple shell command.
    # We'll simulate its effect or assume code is already present.

    {"name": "Setup Node (simulated)", "command": ["echo", "Simulating Node.js setup for version 20..."]},
    # Note: 'actions/setup-node' is a specific GitHub Action.
    # A real Python script would need to manage Node.js installation if not already present.

    {"name": "Install Dependencies", "command": ["npm", "install"]},

    {"name": "Run Tests", "command": ["npm", "test"]},

    {"name": "Build Application", "command": ["npm", "run", "build"]},

    {"name": "Login to Docker Hub", "command": ["docker", "login", "-u", DOCKER_USERNAME, "--password-stdin"],
     "input": DOCKER_PASSWORD},

    {"name": "Build Docker Image", "command": ["docker", "build", "-t", f"{DOCKER_USERNAME}/myapp:latest", "."]},

    {"name": "Push Docker Image", "command": ["docker", "push", f"{DOCKER_USERNAME}/myapp:latest"]},

    {"name": "Deploy to AKS", "command": ["kubectl", "apply", "-f", "deployment.yaml"]}
]

def run_command(step):
    """Executes a shell command and checks for errors."""
    print(f"\n--- Running: {step['name']} ---")
    try:
        # Use subprocess.run for better control and error handling
        # check=True raises an exception for non-zero exit codes
        # text=True decodes stdout/stderr as text
        # capture_output=True captures stdout/stderr
        process = subprocess.run(
            step["command"],
            check=True,
            text=True,
            capture_output=True,
            input=step.get("input", None) # For commands like docker login that take input via stdin
        )
        print("STDOUT:\n", process.stdout)
        if process.stderr:
            print("STDERR:\n", process.stderr) # Errors can still be non-fatal warnings
        print(f"--- Successfully completed: {step['name']} ---")
        return True
    except subprocess.CalledProcessError as e:
        print(f"!!! ERROR in {step['name']} !!!")
        print(f"Command '{' '.join(e.cmd)}' returned non-zero exit code {e.returncode}.")
        print("STDOUT:\n", e.stdout)
        print("STDERR:\n", e.stderr)
        return False
    except FileNotFoundError:
        print(f"!!! ERROR: Command not found for {step['name']} !!!")
        print(f"Please ensure '{step['command'][0]}' is installed and in your PATH.")
        return False
    except Exception as e:
        print(f"!!! An unexpected error occurred during {step['name']} !!!")
        print(e)
        return False

def main():
    print("Starting CI/CD workflow simulation...\n")
    for step in workflow_steps:
        if not run_command(step):
            print(f"\nWorkflow failed at step: {step['name']}")
            sys.exit(1) # Exit with an error code if any step fails
    print("\nCI/CD workflow simulation completed successfully!")

if _name_ == "_main_":
    # Ensure 'deployment.yaml' exists for the kubectl step if running locally for testing
    # You might want to create a dummy file:
    # with open("deployment.yaml", "w") as f:
    #     f.write("apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: myapp\nspec:\n  selector:\n    matchLabels:\n      app: myapp\n  template:\n    metadata:\n      labels:\n        app: myapp\n    spec:\n      containers:\n      - name: myapp\n        image: test/myapp:latest\n        ports:\n        - containerPort: 80")
    main()