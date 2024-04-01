class Optimizers:

    @staticmethod
    def project_completion_0(project):
        project.solver.Minimize(project.solver.Sum([k*project.working_variables[i,j,k] for i in project.workers_indexes for j in project.tasks_indexes for k in project.time_units_indexes]))

    @staticmethod
    def project_completion_1(project):
        infinity = project.solver.infinity()
        y = project.solver.IntVar(0.0, infinity, "y")
        for i in project.worker_indexes:
            for j in project.task_indexes:
                for k in project.time_unit_indexes:
                    project.solver.Add(y >= k*project.working_variables[i,j,k])
        project.solver.Minimize(y)
