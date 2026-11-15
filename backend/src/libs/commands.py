import sys

# The command registry dictionary
COMMANDS = {}

def command(name_or_func=None):
    """
    A flexible decorator to register functions as console commands.
    Can be used as:
        @command
        def test(x): ...
        
        @command("custom_name")
        def test(x): ...
    """
    def decorator(func):
        cmd_name = name_or_func if isinstance(name_or_func, str) else func.__name__
        COMMANDS[cmd_name] = func
        return func

    if callable(name_or_func):
        # Used as @command without parentheses
        func = name_or_func
        COMMANDS[func.__name__] = func
        return func

    return decorator

def _parse_arg(arg_str):
    """Helper to automatically cast string inputs to int, float, or bool where appropriate."""
    if arg_str.lower() == 'true':
        return True
    if arg_str.lower() == 'false':
        return False
    try:
        if '.' in arg_str:
            return float(arg_str)
        return int(arg_str)
    except ValueError:
        return arg_str

def start_console():
    """Starts the infinite console input loop."""
    print("Console active. Type 'help' for commands, or 'exit' to quit.\n")
    
    while True:
        try:
            line = input("> ").strip()
            if not line:
                continue
            
            # Split command name and arguments by whitespace
            parts = line.split()
            cmd_name = parts[0]
            args = [_parse_arg(arg) for arg in parts[1:]]
            
            if cmd_name.lower() in ("exit", "quit"):
                print("Goodbye!")
                break
                
            if cmd_name in COMMANDS:
                try:
                    COMMANDS[cmd_name](*args)
                except TypeError as e:
                    print(f"[-] Invalid arguments for command '{cmd_name}': {e}")
                except Exception as e:
                    print(f"[-] Error executing '{cmd_name}': {e}")
            else:
                print(f"[-] Unknown command: '{cmd_name}'. Type 'help' for a list of commands.")
                
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

# Built-in help command
@command
def help():
    """Lists all registered commands."""
    print("Available commands:")
    for name in sorted(COMMANDS.keys()):
        print(f"  {name}")


# ==========================================
# Example usage / defining commands
# ==========================================
@command
def test(x):
    print("test:", x, f"(type: {type(x).__name__})")

@command("add")
def sum_numbers(a, b):
    print(f"Result: {a} + {b} = {a + b}")


if __name__ == "__main__":
    start_console()
