from datetime import date
from summarize import summarize_transcript

transcript = """
Ali: Good morning everyone. Today we will discuss the quotation for our new client, ABC Traders.
Sara: I have reviewed their requirements. They want 25 laptops.
Ali: Okay. Sara, please prepare and send the quotation by Friday.
Sara: Sure, I will get it done. We cannot offer more than a 5% discount.
Ali: Agreed. And Usman, please follow up with the client by phone next Monday.
Usman: Okay, I will do that.
Ali: Finally, we decided that delivery will be within 2 weeks.
"""

today = date.today()
result = summarize_transcript(
    transcript,
    meeting_date=today.isoformat(),
    weekday=today.strftime("%A"),
)

print(result.model_dump_json(indent=2))