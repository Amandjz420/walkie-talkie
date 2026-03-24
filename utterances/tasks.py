from celery import shared_task

from utterances.services import UtteranceProcessingService


@shared_task
def process_utterance_task(utterance_id: int) -> None:
    UtteranceProcessingService.process(utterance_id=utterance_id)
