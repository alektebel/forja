"""The shell's own policy, as data.

Every number, name and list a stage reads a rule from lives here and nowhere else,
so a stage that reads a rule reads the value the contract pinned and not a twin of
it. The module is frozen: it holds data and the two sentences that name it, and
nothing that runs.
"""

POLICY_VERSION = "shell-policy-1"

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_CANNOT_EXECUTE = 126          # found, but not executable
EXIT_NOT_FOUND = 127               # no such command
EXIT_BAD_USAGE = 2                 # a builtin's own complaint
SIGNAL_STATUS_BASE = 128           # a signalled process answers 128 + number

SIGNAL_NAMES = ("HUP", "INT", "QUIT", "TERM", "CHLD", "STOP", "CONT")
SIGNAL_NUMBERS = {"HUP": 1, "INT": 2, "QUIT": 3, "TERM": 15, "CHLD": 17,
                  "STOP": 19, "CONT": 18}

OPERATORS = ("|", "&&", "||", ";", "&", ">", ">>", "<", "<<", "2>", "2>&1")
ASSIGNMENT = "="                    # NAME=value, and where it may appear
SEPARATORS = (";", "&", "&&", "||", "|")

EXPANSION_ORDER = ("parameter", "tilde", "split", "glob", "quote-removal")

ERREXIT_EXEMPTIONS = ("condition", "and-or-left", "negated", "pipeline-but-last",
                      "while-condition", "if-condition")

BUILTINS = ("cd", "exit", "export", "kill", "read", "set", "shift", "trap",
            "unset", "wait", ":")
STATE_BUILTINS = ("cd", "export", "read", "set", "shift", "trap", "unset")

LIMITS = {"words": 4096, "depth": 32, "glob": 1024, "status": 255,
          "var_name": 64, "var_value": 4096}
