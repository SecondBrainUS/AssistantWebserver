

"""



db: Session = Depends(get_db)
# timescaledb: Session = Depends(timescaledb_get_db)
@router.post("/test")
async def post_run(
    text: Optional[str] = Form(None, description="Text based prompt"),
    audio: Optional[UploadFile] = File(None, description="Audio file"),
    images: Optional[List[UploadFile]] = File(None, description="Array of image files"),
    video: Optional[UploadFile] = File(None, description="Video file")
):
    return {"message": "Test"}
"""