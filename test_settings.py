from pynch.db import DB


settings = {'Base_db': DB('test', 'localhost', 27017),
            'BugStomper_db': DB('test', 'localhost', 27017)}
