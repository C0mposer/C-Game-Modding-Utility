import subprocess

# Open a new command line pipe, and return (stdout, stderr).
def OpenPipeWithStdStreams(command: str):
    command_outputs = subprocess.run(command, shell=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    stdout = command_outputs.stdout
    stderr = command_outputs.stderr

    return stdout, stderr
