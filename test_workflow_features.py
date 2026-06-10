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
        schedule_visual = result['steps'][0]['visual']
        visual = result['steps'][1]['visual']

        self.assertTrue(result['post_plan'])
        self.assertEqual(result['stage'], 'delivered')
        self.assertEqual(schedule_visual['type'], 'calendar')
        self.assertEqual(schedule_visual['days'][2]['kind'], 'mobility')
        self.assertEqual(schedule_visual['days'][2]['label'], '요가 20분')
        self.assertIn(
            '3일차 운동을 요가 20분으로 변경',
            visual['revisions'],
        )
        revision_card = next(
            card for card in visual['cards'] if card['title'] == '수정 반영'
        )
        self.assertIn('요가 20분', revision_card['body'])
        self.assertNotIn('바꿔줘', revision_card['body'])
        self.assertNotIn('바꿔줘', result['steps'][1]['content'])

        schedule = self.manager._step_visual(
            conversation_id, 'schedule', has_diet=True
        )
        day_three = schedule['days'][2]
        self.assertEqual(day_three['kind'], 'mobility')
        self.assertEqual(day_three['label'], '요가 20분')

    def test_check_day_edit_changes_calendar_instead_of_echoing_request(self):
        conversation_id = self._seed_weight_profile()
        self.db.add_workflow_state(
            conversation_id=conversation_id,
            stage='schedule',
            user_input='7일차에 점검하자',
            gpt_response='수정됨',
            intervention_type='modify',
            autonomy_level='low',
        )

        visual = self.manager._step_visual(
            conversation_id, 'schedule', has_diet=True,
            revision='7일차에 점검하자',
        )
        check_days = [
            item['day'] for item in visual['days'] if item['tag']
        ]

        self.assertEqual(check_days, [7])
        self.assertEqual(visual['revision'], '7일차에 컨디션 점검 설정')
        self.assertNotIn('하자', visual['revision'])

    def test_exercise_availability_is_recognized_without_level_answer(self):
        conversation_id = self._seed_weight_profile()
        for message in ('승인', '계속 진행', '운동 가능 일정은 앞에서 입력했어요'):
            self.db.add_message(conversation_id, 'user', message)

        context = self.manager._exercise_context(conversation_id)
        visual = self.manager._step_visual(
            conversation_id, 'workout', has_diet=True
        )
        rendered = ' '.join(card['body'] for card in visual['cards'])

        self.assertEqual(
            [item['day'] for item in context['availability']],
            ['월', '수', '토'],
        )
        self.assertIn('입력한 운동 가능 일정 확인됨', rendered)
        self.assertNotIn('정보 없음', rendered)

    def test_grocery_step_omits_duplicate_text_body(self):
        conversation_id = self._seed_weight_profile()
        result = self.manager._run_single_phase(
            conversation_id, 'control', 'grocery',
            '장보기 단계 진행', 'low',
        )

        self.assertEqual(result['steps'][0]['content'], '')
        self.assertEqual(result['steps'][0]['visual']['type'], 'grocery')

    def test_all_quick_edit_examples_change_their_visual_data(self):
        conversation_id = self._seed_weight_profile()

        self.db.add_workflow_state(
            conversation_id=conversation_id,
            stage='calc',
            user_input='칼로리를 조금 낮춰줘',
            gpt_response='수정됨',
            intervention_type='modify',
            autonomy_level='low',
        )
        self.db.add_workflow_state(
            conversation_id=conversation_id,
            stage='calc',
            user_input='단백질 비중을 높여줘',
            gpt_response='수정됨',
            intervention_type='modify',
            autonomy_level='low',
        )
        calc = self.manager._step_visual(conversation_id, 'calc')
        macros = {item['label']: item['pct'] for item in calc['items']}
        self.assertEqual(calc['kcal'], 1800)
        self.assertEqual(macros['단백질'], 35)

        self.db.add_workflow_state(
            conversation_id=conversation_id,
            stage='calc',
            user_input='단백질을 40%로 맞춰줘',
            gpt_response='수정됨',
            intervention_type='modify',
            autonomy_level='low',
        )
        calc = self.manager._step_visual(conversation_id, 'calc')
        macros = {item['label']: item['pct'] for item in calc['items']}
        self.assertEqual(macros['단백질'], 40)
        self.assertEqual(sum(macros.values()), 100)

        self.db.add_workflow_state(
            conversation_id=conversation_id,
            stage='meal',
            user_input='저녁을 더 가볍게 바꿔줘',
            gpt_response='수정됨',
            intervention_type='modify',
            autonomy_level='low',
        )
        meal = self.manager._step_visual(conversation_id, 'meal')
        dinner = next(card for card in meal['cards'] if card['title'] == '저녁')
        self.assertIn('두부 샐러드', dinner['body'])

        self.db.add_workflow_state(
            conversation_id=conversation_id,
            stage='workout',
            user_input='휴식일을 토·일로 바꿔줘',
            gpt_response='수정됨',
            intervention_type='modify',
            autonomy_level='low',
        )
        workout = self.manager._step_visual(conversation_id, 'workout')
        schedule = self.manager._step_visual(conversation_id, 'schedule')
        rest_card = next(card for card in workout['cards'] if card['title'] == '휴식일')
        self.assertIn('토·일요일', rest_card['body'])
        self.assertEqual(schedule['days'][5]['kind'], 'rest')
        self.assertEqual(schedule['days'][6]['kind'], 'rest')

        self.db.add_workflow_state(
            conversation_id=conversation_id,
            stage='sleep',
            user_input='취침을 23:00, 기상은 06:30으로 바꿔줘',
            gpt_response='수정됨',
            intervention_type='modify',
            autonomy_level='low',
        )
        sleep = self.manager._step_visual(conversation_id, 'sleep')
        schedule = self.manager._step_visual(conversation_id, 'schedule')
        self.assertEqual(sleep['bedtime'], '23:00')
        self.assertEqual(sleep['waketime'], '06:30')
        self.assertIn('취침 23:00', schedule['sleep_summary'])
        self.assertIn('기상 06:30', schedule['sleep_summary'])

        self.db.add_workflow_state(
            conversation_id=conversation_id,
            stage='sleep',
            user_input='카페인 관련 팁을 바꿔줘',
            gpt_response='수정됨',
            intervention_type='modify',
            autonomy_level='low',
        )
        sleep = self.manager._step_visual(conversation_id, 'sleep')
        self.assertIn('취침 8시간 전', sleep['tips'][1])

        self.db.add_workflow_state(
            conversation_id=conversation_id,
            stage='grocery',
            user_input='두부를 빼고 연어를 추가해줘',
            gpt_response='수정됨',
            intervention_type='modify',
            autonomy_level='low',
        )
        grocery = self.manager._step_visual(conversation_id, 'grocery')
        first_week = ' '.join(
            card['body'] for card in grocery['weeks'][0]['cards']
        )
        self.assertNotIn('두부', first_week)
        self.assertIn('연어', first_week)

    def test_post_plan_sleep_edit_returns_updated_sleep_card(self):
        conversation_id = self._seed_weight_profile()
        self.db.add_workflow_state(
            conversation_id=conversation_id,
            stage='delivered',
            gpt_response='초기 계획',
            autonomy_level='low',
        )

        result = self.manager.process_message(
            conversation_id, '취침을 22:30으로 바꿔줘'
        )

        self.assertEqual(result['steps'][0]['visual']['type'], 'sleep')
        self.assertEqual(result['steps'][0]['visual']['bedtime'], '22:30')
        self.assertEqual(result['steps'][1]['visual']['type'], 'summary')
        sleep_card = next(
            card for card in result['steps'][1]['visual']['cards']
            if card['title'] == '수면'
        )
        self.assertIn('취침 22:30', sleep_card['body'])

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
