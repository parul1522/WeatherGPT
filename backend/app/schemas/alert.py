from pydantic import BaseModel


class Alert(BaseModel):
    id: str
    severity: str
    title: str
    description: str
