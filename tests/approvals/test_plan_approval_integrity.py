import unittest
from copy import deepcopy

from resource_planning_agent.storage.plan_store import create_plan_draft
from resource_planning_agent.planning.plan_validation import validate_plan_for_assignment
from resource_planning_agent.planning.resource_proposal import OTHER_TEAM_EMPLOYEES, propose_resources
from resource_planning_agent.storage.database import PLANNING_PERIOD


class TestPlanApprovalIntegrity(unittest.TestCase):
    def setUp(self):
        proposal = propose_resources(
            employees=OTHER_TEAM_EMPLOYEES,
            required_skill='backend',
            shortage=8,
            excluded_names=['Ada', 'Bora'],
        )
        self.plan = create_plan_draft('DEMO-PROJECT-001', proposal)
        self.plan['status'] = 'approved'
        for approval in self.plan['required_approvals']:
            approval['status'] = 'approved'

    def validate(self, plan):
        return validate_plan_for_assignment(
            plan=plan,
            employees=deepcopy(OTHER_TEAM_EMPLOYEES),
            planning_period=PLANNING_PERIOD,
        )

    def test_valid_approval_set_passes(self):
        self.assertTrue(self.validate(self.plan)['checks_passed'])

    def test_missing_team_manager_approval_rejected(self):
        self.plan['required_approvals'] = [
            item for item in self.plan['required_approvals']
            if not (item['role'] == 'team_manager' and item['scope'] == 'Platform')
        ]
        result = self.validate(self.plan)
        self.assertFalse(result['checks_passed'])
        self.assertTrue(any('onay kapsam' in issue.lower() for issue in result['issues']))

    def test_wrong_project_manager_scope_rejected(self):
        project_approval = self.plan['required_approvals'][0]
        project_approval['scope'] = 'OTHER-PROJECT'
        result = self.validate(self.plan)
        self.assertFalse(result['checks_passed'])

    def test_duplicate_approval_rejected(self):
        self.plan['required_approvals'].append(deepcopy(self.plan['required_approvals'][0]))
        result = self.validate(self.plan)
        self.assertFalse(result['checks_passed'])


if __name__ == '__main__':
    unittest.main()
