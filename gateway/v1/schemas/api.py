import random
from pydantic import BaseModel, Field
from typing import Optional, Union, List, Literal


class SearchRequest(BaseModel):
    query: str = Field(..., description="The query to scrape")


class InlineImage(BaseModel):
    title: str = Field(..., description="Alt text or title of the image")
    url: str = Field(..., description="URL of the image")
    width: Optional[int] = Field(None, description="Width of the image in pixels")
    height: Optional[int] = Field(None, description="Height of the image in pixels")


class ParagraphBlock(BaseModel):
    type: Literal["paragraph"] = Field(..., description="Block type identifier")
    snippet: str = Field(..., description="Text content of the paragraph")


class ListBlock(BaseModel):
    type: Literal["list"] = Field(..., description="Block type identifier")
    items: List[str] = Field(..., description="List of text items")


class Reference(BaseModel):
    title: str = Field(..., description="Title of the reference")
    link: str = Field(..., description="URL of the reference")
    snippet: str = Field("", description="Contextual snippet from the reference")
    source: str = Field(..., description="Domain name of the reference source")
    thumbnail: str = Field("", description="Thumbnail image URL")
    favicon: str = Field("", description="Favicon URL")
    index: int = Field(..., description="Position index of the reference")


TextBlock = Union[ParagraphBlock, ListBlock]

BARN_ANIMALS = ["cows", "sheep", "pigs", "chickens", "horses", "dogs", "cats", "rabbits", "fish", "birds"]

class Metadata(BaseModel):
    credits_used: str = Field("0", description="Credits used for the request")
    version: str = Field("0.1.0", description="Version of the API")
    
    def set_credits_used(self):
        usage = random.randint(1, 100)
        self.credits_used = random.choice(BARN_ANIMALS) + " " + str(usage)


class SearchResponse(BaseModel):
    text_blocks: List[TextBlock] = Field(
        default_factory=list,
        description="Structured text content blocks (paragraphs and lists)"
    )
    references: List[Reference] = Field(
        default_factory=list,
        description="Reference links with metadata"
    )
    inline_images: List[InlineImage] = Field(
        default_factory=list,
        description="Images found in the content with metadata"
    )
    
    metadata: Metadata = Field(
        default_factory=Metadata,
        description="Metadata for the request"
    )