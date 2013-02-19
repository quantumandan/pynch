from pynch.db import DB


settings = {'Base_db': DB('test', 'localhost', 27017),
            'Gardener_db': DB('test', 'localhost', 27017),
            'Garden_db': DB('test', 'localhost', 27017)}
