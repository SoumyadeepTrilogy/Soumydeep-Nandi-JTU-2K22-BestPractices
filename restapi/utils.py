import time

def calculate_time(func):
    def inner(*args,**kwargs):
        start = int(time.time() * 1000.0)
        result = func(*args,**kwargs)  
        logger.info(f'Function {str(func.__name__)} executed in {(time.time() * 1000.0) - start} ms')
        return result
    return inner
