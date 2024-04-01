from datetime import timedelta

import scheduler.engine as sched

day = timedelta(days=1)

# https://developers.google.com/optimization/mip/mip_example?hl=it

resource_0 = sched.Resource('resource 0')
resource_1 = sched.Resource('resource 1')
resource_2 = sched.Resource('resource 2')
resource_3 = sched.Resource('resource 3')
resource_4 = sched.Resource('resource 4')

worker_0 = sched.Worker('worker 0', symbol='*')
worker_1 = sched.Worker('worker 1', symbol='-')
worker_2 = sched.Worker('worker 2', symbol='+')

tasks = []

tasks.append(sched.Task('task 0', inputs = [], outputs = [resource_0], worker = worker_0, time = 5*day))
tasks.append(sched.Task('task 1', inputs = [], outputs = [resource_3], worker = worker_0, time = 24*day))
tasks.append(sched.Task('task 2', inputs = [resource_0], outputs = [resource_1], worker = worker_1, time = 5*day))
tasks.append(sched.Task('task 3', inputs = [resource_1], outputs = [resource_2], worker = worker_0, time = 5*day))
tasks.append(sched.Task('task 4', inputs = [resource_2], outputs = [resource_4], worker = worker_2, time = 9*day))
tasks.append(sched.Task('task 5', inputs = [resource_3, resource_4], outputs = [], worker = worker_1, time = 8*day))

try:
    print('\nInitializing project...\n')
    project = sched.Project(tasks, day)
    project.init_tasks_dependencies()
    project.init_solver(sched.Optimizers.project_completion_0, 'SCIP')
    print('... OK, running solver...\n')
    project.solve()
    print('... OK, showing results:\n')
    project.show_tasks_activity()
    # project.show_workers_activity()
    # project.show_tasks_dependencies()
except sched.Error as e:
    print(f'... KO: {e}.\n')
