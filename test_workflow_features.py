import os
import tempfile
import unittest

from database.db_manager import DBManager
from services.mock_gpt_service import MockGPTService
from services.workflow_manager import WorkflowManager


class WorkflowFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = DBManager(os.path.join(self.temp_dir.name, 'test.db'))
        self.manager = WorkflowManager(MockGPTService(), self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _seed_habit_profile(self):
        conversation_id = self.db.create_conversation(
            condition='control', autonomy_level='low'
        )
        messages = [
            '2주 건강 루틴을 만들고 싶어요',
            '규칙적인 운동 습관을 만들고 싶어요',
            '운동을 거의 안 해요',
            '요가나 스트레칭을 선호해요',
            '운동 가능: 화 저녁, 목 오전, 토 오전·오후',
            '키와 몸무게는 생략할게요',
        ]
        for message in messages:
            self.db.add_message(conversation_id, 'user', message)
        return conversation_id

    def _seed_weight_profile(self):
        conversation_id = self.db.create_conversation(
            condition='control', autonomy_level='low'
        )
        messages = [
            '2주 건강 루틴을 만들고 싶어요',
            '체중 감량도 함께 고려하고 싶어요',
            '2주간 약 1~2kg 정도 빼고 싶어요',
            '주로 앉아서 생활해요',
            '특별히 가리는 음식은 없어요',
            '운동 가능: 월 저녁, 수 저녁, 토 오전',
            '키 170cm, 몸무게 70kg',
        ]
        for message in messages:
            self.db.add_message(conversation_id, 'user', message)
        return conversation_id

    def test_grocery_has_two_distinct_weeks_and_budgets(self):
        conversation_id = self._seed_weight_profile()
        visual = self.manager._step_visual(
            conversation_id, 'grocery', has_diet=True
        )

        self.assertEqual(visual['type'], 'grocery')
        self.assertEqual(len(visual['weeks']), 2)
        self.assertIn('원', visual['weeks'][0]['budget'])
        self.assertIn('원', visual['weeks'][1]['budget'])
        self.assertNotEqual(
            visual['weeks'][0]['cards'][0]['body'],
            visual['weeks'][1]['cards'][0]['body'],
        )
        self.assertIn('총예산', visual['total_budget'])

    def test_workout_uses_current_level_and_available_slots(self):
        conversation_id = self._seed_habit_profile()
        visual = self.manager._step_visual(
            conversation_id, 'workout', has_diet=False
        )
        rendered = ' '.join(
            f"{card['title']} {card['body']}" for card in visual['cards']
        )

        self.assertIn('운동을 거의 하지 않음', rendered)
        self.assertIn('요가·스트레칭', rendered)
        self.assertIn('화요일 저녁', rendered)
        self.assertIn('목요일 오전', rendered)
        self.assertIn('토요일 오전·오후', rendered)
        self.assertNotIn('월요일', rendered)

    def test_weight_summary_uses_goal_specific_diet_strategy(self):
        conversation_id = self._seed_weight_profile()
        schedule = self.manager._step_visual(
            conversation_id, 'schedule', has_diet=True
        )
        delivery = self.manager._step_visual(
            conversation_id, 'delivery', has_diet=True
        )
        diet_card = next(
            card for card in delivery['cards'] if card['title'] == '식단'
        )

        self.assertIn('단백질', schedule['diet_summary'])
        self.assertIn('포화지방', diet_card['body'])
        self.assertNotIn('균형식', schedule['diet_summary'])
        self.assertNotIn('균형식', diet_card['body'])

    def test_post_plan_edit_is_visible_in_updated_summary(self):
        conversation_id = self._seed_weight_profile()
        self.db.add_workflow_state(
            conversation_id=conversation_id,
            stage='delivered',
            gpt_response='초기 계획',
            autonomy_level='low',
        )

        result = self.manager.process_message(
            conversation_id, '3일차 운동을 요가 20분으로 바꿔줘'
        )
        visual = result['steps'][0]['visual']

        self.assertTrue(result['post_plan'])
        self.assertEqual(result['stage'], 'delivered')
        self.assertIn(
            '3일차 운동을 요가 20분으로 바꿔줘',
            visual['revisions'],
        )
        revision_card = next(
            card for card in visual['cards'] if card['title'] == '수정 반영'
        )
        self.assertIn('요가 20분', revision_card['body'])
        self.assertIn(
            '3일차 운동을 요가 20분으로 바꿔줘',
            result['steps'][0]['content'],
        )

    def test_control_autonomous_finish_still_offers_final_edit(self):
        conversation_id = self._seed_habit_profile()
        self.db.add_workflow_state(
            conversation_id=conversation_id,
            stage='workout',
            gpt_response='운동 루틴',
            autonomy_level='low',
        )

        result = self.manager.process_message(
            conversation_id, '이제 알아서 끝까지 진행해줘'
        )

        self.assertEqual(result['stage'], 'delivered')
        self.assertTrue(result['post_plan'])
        self.assertFalse(result['controls_enabled'])


if __name__ == '__main__':
    unittest.main()
