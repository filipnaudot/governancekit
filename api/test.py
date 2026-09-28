# main.py
from fastapi import FastAPI

app = FastAPI()



@app.get("/weather/{city}")
def get_weather(city: str):
    # In a real app you'd look this up in a database
    # or call an external weather service here
    return {"city": city, "temp": 14, "condition": "cloudy"}


@app.get("/test/{something}")
def say_something(something: str):
    return {"promt": something}

@app.get("/test2/{something}")
def say_something2(something: str):
    return {"promt2": something}


