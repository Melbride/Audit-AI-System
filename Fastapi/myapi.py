from fastapi import FastAPI, Path
from typing import Optional
from pydantic import BaseModel
app = FastAPI()

#path parameters
students = {
    1: {
        "name": "John",
        "age": 17,
        "class": "year 12"
    }
}


#create an endpoint
@app.get("/")
def index():
    return {"name": "First Data"}

@app.get("/get-student/{student_id}")
def get_student(student_id: int = Path(..., description="The ID of the student you want to view", gt=0, lt=3)):
    return students[student_id]

#query parameters
@app.get("/get-by-name")
def get_student(*,name: Optional[str] = None, test: int):
    for student_id in students:
        if students[student_id]["name"] == name:
            return students[student_id]
    return {"Data": "Not found"}
    

#Request body and the post method
#request body is used to send data to the server in the form of json, xml, etc. and it is used to create or update a resource on the server. The post method is used to create a resource on the server.
class Student(BaseModel):
    name: str
    age: int
    year: str

    

@app.post("/create-student/{student_id}")
def create_student(student_id: int, student : Student):
    if student_id in students:
        return {"Error": "Student already exists"}
    students[student_id] = student
    return students[student_id]


#put method
#put method is used to update a resource on the server. It is used to update a resource completely. It

class UpdateStudent(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    year: Optional[str] = None
    
@app.put("/update-student/{student_id}")
def update_student(student_id: int, student: UpdateStudent):
    if student_id not in students:
        return {"Error": "Student does not exist"}
    
    if student.name != None:
        students[student_id].name = student.name
    
    if student.age != None:
        students[student_id].age = student.age
    
    if student.year != None:
        students[student_id].year = student.year
    return students[student_id]

#delete method
#delete method is used to delete a resource on the server. It is used to delete a resource completely.
@app.delete("/delete-student/{student_id}")
def delete_student(student_id: int):
    if student_id not in students:
        return {"Error": "Student does not exist"}
    del students[student_id]
    return {"Message": "Student deleted successfully"}







