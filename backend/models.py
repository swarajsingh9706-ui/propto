from datetime import datetime, timezone
from typing import Optional, List, Any, Annotated
from pydantic import BaseModel, Field, BeforeValidator, ConfigDict, EmailStr
from bson import ObjectId


def _to_str(v: Any) -> Any:
    if isinstance(v, ObjectId):
        return str(v)
    return v


PyObjectId = Annotated[str, BeforeValidator(_to_str)]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, extra="ignore")
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    @classmethod
    def from_mongo(cls, doc: dict):
        if not doc:
            return None
        return cls(**doc)

    def to_mongo(self, exclude_none: bool = True) -> dict:
        data = self.model_dump(by_alias=True, exclude_none=exclude_none)
        data.pop("_id", None)
        return data


# ---------- Auth ----------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: str
    name: str
    role: str  # super_admin | society_admin
    society_id: Optional[str] = None


# ---------- Society ----------
class SocietyCreate(BaseModel):
    name: str
    code: str
    address: Optional[str] = ""
    city: Optional[str] = ""
    towers: List[str] = []
    admin_name: Optional[str] = ""
    admin_email: Optional[EmailStr] = None
    admin_password: Optional[str] = None


class SocietyUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    towers: Optional[List[str]] = None
    active: Optional[bool] = None
    admin_email: Optional[str] = None
    admin_password: Optional[str] = None


# ---------- Vendor ----------
class VendorCreate(BaseModel):
    name: str
    phone: str
    categories: List[str] = []
    availability: bool = True
    active: bool = True
    priorities: dict = {}


class VendorUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    categories: Optional[List[str]] = None
    availability: Optional[bool] = None
    active: Optional[bool] = None
    priorities: Optional[dict] = None


# ---------- Resident ----------
class ResidentCreate(BaseModel):
    name: str
    phone: str
    flat: str
    tower: Optional[str] = ""
    status: Optional[str] = "Owner"


class ResidentUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    flat: Optional[str] = None
    tower: Optional[str] = None
    status: Optional[str] = None


# ---------- Ticket ----------
class TicketAssign(BaseModel):
    vendor_id: str


class TicketUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None


class PublicReassign(BaseModel):
    target: str  # "vendor" | "manager"
    category: Optional[str] = None


# ---------- WhatsApp Simulator ----------
class SimulateMessage(BaseModel):
    phone: str
    text: str
    flat: Optional[str] = None


class TestSend(BaseModel):
    phone: str


class GroupConnect(BaseModel):
    group_name: str
    group_id: str


# ---------- HITL ----------
class ReviewDecision(BaseModel):
    action: str  # approve | reject
    category: Optional[str] = None
    flat: Optional[str] = None
    tower: Optional[str] = None
    priority: Optional[str] = None
    description: Optional[str] = None


# ---------- Suggestions ----------
class SuggestionCreate(BaseModel):
    title: str
    category: Optional[str] = "General"
    author_name: Optional[str] = ""
    flat: Optional[str] = ""


class SuggestionStatusUpdate(BaseModel):
    status: str


class SuggestionVote(BaseModel):
    vote: str  # yes | no
