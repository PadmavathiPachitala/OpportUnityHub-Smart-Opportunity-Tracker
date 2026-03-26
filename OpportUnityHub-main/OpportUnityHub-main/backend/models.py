from pydantic import BaseModel
from typing import Optional

class Opportunity(BaseModel):
    id: str
    title: str
    organization: str
    type: str          # internship | hackathon | job
    location: str
    deadline: Optional[str] = "N/A"
    stipend: Optional[str] = "N/A"
    apply_link: str
    description: Optional[str] = ""
    source: str        # internshala | devpost | unstop | remotive
    domain: Optional[str] = "general"
    verified: bool = True
    logo: Optional[str] = ""
    