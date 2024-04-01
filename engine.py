from ortools.linear_solver import pywraplp
import networkx as nx
import matplotlib.pyplot as plt

class ErrorTypes:
    TASKS_IDENTIFIERS = 0
    WORKERS_IDENTIFIERS = 1
    RESOURCES_IDENTIFIERS = 2
    COLLIDING_OUTPUTS = 3
    NOT_INSTANTIABLE_SOLVER = 4
    CYCLIC_GRAPH = 5
    NOT_LINKED_INPUT = 6
    UNFEASIBLE_PROBLEM = 7
    NOT_INITIALIZED_SOLVER = 8
    NOT_SOLVED_PROBLEM = 9

class Error(Exception):
    def __init__(self, t, *args):
        match t:
            case ErrorTypes.TASKS_IDENTIFIERS:
                self.details = f"more tasks have the same identifier '{args[0].identifier}'"
            case ErrorTypes.WORKERS_IDENTIFIERS:
                self.details = f"more workers have the same identifier '{args[0].identifier}'"
            case ErrorTypes.RESOURCES_IDENTIFIERS:
                self.details = f"more resources have the same identifier '{args[0].identifier}'"
            case ErrorTypes.COLLIDING_OUTPUTS:
                self.details = f"resource '{args[0].identifier}' is produced by both '{args[1].identifier}' and '{args[2].identifier}'"
            case ErrorTypes.NOT_INSTANTIABLE_SOLVER:
                self.details = f"solver '{args[0]}' can't be instantiated"
            case ErrorTypes.CYCLIC_GRAPH:
                self.details = "found cyclic dependencies"
            case ErrorTypes.NOT_LINKED_INPUT:
                self.details = f"input '{args[0].identifier}' can't be linked to any output"
            case ErrorTypes.UNFEASIBLE_PROBLEM:
                self.details = "scheduling problem is unfeasible"
            case ErrorTypes.NOT_INITIALIZED_SOLVER:
                self.details = "solver hasn't been initialized"
            case ErrorTypes.NOT_SOLVED_PROBLEM:
                self.details = "scheduling problem hasn't been solved"
        super().__init__(self.details)

class Resource:

    def __init__(self, identifier) -> None:
        self.identifier = identifier

class Worker:

    def __init__(self, identifier, symbol="*") -> None:
        self.identifier = identifier
        if len(symbol) == 1:
            self.symbol = symbol
        else:
            self.symbol = "*"

class Task:

    def __init__(self, identifier, inputs, outputs, worker, time, symbol="*") -> None:
        self.identifier = identifier
        self.inputs = inputs
        self.outputs = outputs
        self.worker = worker
        self.time = time
        if len(symbol) == 1:
            self.symbol = symbol
        else:
            self.symbol = "*"

class Project:

    def __init__(self, tasks, time_unit) -> None:
        self.tasks = []
        self.workers = []
        self.resources = {}
        tasks_identifiers = []
        workers_identifiers = []
        resources_identifiers = []
        self.time_unit = time_unit
        self.time_units = 0
        for task in tasks:
            if not task in self.tasks:
                if not task.identifier in tasks_identifiers:
                    self.tasks.append(task)
                    tasks_identifiers.append(task.identifier)
                    self.time_units += task.time // self.time_unit
                else:
                    raise Error(ErrorTypes.TASKS_IDENTIFIERS, task)
            if not task.worker in self.workers:
                if not task.worker.identifier in workers_identifiers:
                    self.workers.append(task.worker)
                    workers_identifiers.append(task.worker.identifier)
                else:
                    raise Error(ErrorTypes.WORKERS_IDENTIFIERS, task.worker)
            for resource in task.inputs + task.outputs:
                if not resource in self.resources:
                    if not resource.identifier in resources_identifiers:
                        self.resources[resource] = task
                        resources_identifiers.append(resource.identifier)
                    else:
                        raise Error(ErrorTypes.RESOURCES_IDENTIFIERS, resource)
                elif resource in task.outputs:
                    raise Error(ErrorTypes.COLLIDING_OUTPUTS, resource, self.resources[resource], task)
        self.identifier_max_length = 0
        for identifier in tasks_identifiers + workers_identifiers + resources_identifiers:
            if len(identifier) > self.identifier_max_length:
                self.identifier_max_length = len(identifier)
        tasks_identifiers = None
        workers_identifiers = None
        resources_identifiers = None
        self.tasks_indexes = range(len(self.tasks))
        self.workers_indexes = range(len(self.workers))
        self.time_units_indexes = range(self.time_units)
        self.solver = None
        self.working_variables = {} # self.working_variables[i,j,k] is an array of 0-1 variables, which will be 1 if worker i works on task j in unit of time k
        self.completion_variables = {} # self.completion_variables[j,k] is an array of 0-1 variables, which can be 1 only if task j completed before unit of time k
        self.solved = False
        self.graph = None
        self.linked_resources = []

    def init_tasks_dependencies(self) -> None:
        self.graph = nx.DiGraph()
        for consumer in self.tasks:
            for i in consumer.inputs:
                linked = False
                for producer in self.tasks:
                    for o in producer.outputs:
                        if i == o:
                            self.graph.add_edges_from([(producer.identifier, consumer.identifier)])
                            if not i in self.linked_resources:
                                self.linked_resources.append(i)
                            linked = True
                            break
                    if linked:
                        break
                if not linked:
                    raise Error(ErrorTypes.NOT_LINKED_INPUT, i)
        if not nx.is_directed_acyclic_graph(self.graph):
            raise Error(ErrorTypes.CYCLIC_GRAPH)

    def show_tasks_dependencies(self) -> None:
        if not self.graph is None:
            pos = nx.spring_layout(self.graph)
            nx.draw_networkx_nodes(self.graph, pos, cmap=plt.get_cmap("jet"), node_size = 500)
            nx.draw_networkx_labels(self.graph, pos)
            nx.draw_networkx_edges(self.graph, pos, arrows=True)
            plt.show()

    def init_solver(self, opt, impl) -> None:
        self.solver = pywraplp.Solver.CreateSolver(impl)
        if not self.solver:
            self.solver = None
            raise Error(ErrorTypes.NOT_INSTANTIABLE_SOLVER, impl)
        for i in self.workers_indexes:
            for j in self.tasks_indexes:
                for k in self.time_units_indexes:
                    self.working_variables[i,j,k] = self.solver.IntVar(0, 1, "work")
                    if not self.tasks[j].worker == self.workers[i]:
                        self.solver.Add(self.working_variables[i,j,k] == 0) # Only worker i can work on task j
            for k in self.time_units_indexes:
                self.solver.Add(self.solver.Sum([self.working_variables[i,j,k] for j in self.tasks_indexes]) <= 1) # Each worker is assigned to at most 1 task
        for j in self.tasks_indexes:
            self.solver.Add(self.solver.Sum([self.working_variables[i,j,k] for i in self.workers_indexes for k in self.time_units_indexes]) == self.tasks[j].time // self.time_unit) # Task j must execute for self.tasks[j].time
            for k in self.time_units_indexes:
                self.completion_variables[j,k] = self.solver.IntVar(0, 1, "completed")
                self.solver.Add(self.solver.Sum([self.working_variables[i,j,kk] for i in self.workers_indexes for kk in range(k)]) >= (self.tasks[j].time // self.time_unit) * self.completion_variables[j,k]) # self.completion_variables[j,k] can be 1 only if task j completed before unit of time k
            if not self.graph is None and self.tasks[j].identifier in list(self.graph.nodes):
                ancestors = []
                for ancestor_identifier in list(nx.ancestors(self.graph, self.tasks[j].identifier)):
                    for task in self.tasks:
                        if task.identifier == ancestor_identifier:
                            ancestors.append(task)
                            break
                ancestor_indexes = []
                for task in ancestors:
                    for jj in self.tasks_indexes:
                        if self.tasks[jj] == task:
                            ancestor_indexes.append(jj)
                            break
                for k in self.time_units_indexes:
                    for i in self.workers_indexes:
                        self.solver.Add(self.solver.Sum([self.completion_variables[jj,k] for jj in ancestor_indexes]) >= len(ancestor_indexes)*self.working_variables[i,j,k]) # Task j can execute only after all its ancestors have completed
        opt(self)

    def solve(self) -> None:
        if not self.solver is None:
            # print(f"Solving with {self.solver.SolverVersion()}")
            status = self.solver.Solve()
            if not status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
                raise Error(ErrorTypes.UNFEASIBLE_PROBLEM)
            else:
                self.solved = True
            # print(f"Total cost = {self.solver.Objective().Value()}\n")
        else:
            raise Error(ErrorTypes.NOT_INITIALIZED_SOLVER)

    def show_tasks_activity(self, mode="text") -> None:
        if self.solved:
            if mode == "text":
                for j in self.tasks_indexes:
                    msg = f"{self.tasks[j].identifier + " "*(self.identifier_max_length-len(self.tasks[j].identifier))} "
                    for k in self.time_units_indexes:
                        symbol = " "
                        for i in self.workers_indexes:
                            if self.working_variables[i,j,k].solution_value() > 0.5:
                                symbol = self.workers[i].symbol
                                break
                        msg += symbol
                    print(f"{msg}\n")
        else:
            raise Error(ErrorTypes.NOT_SOLVED_PROBLEM)

    def show_workers_activity(self, mode="text") -> None:
        if self.solved:
            if mode == "text":
                for i in self.workers_indexes:
                    msg = f"{self.workers[i].identifier + " "*(self.identifier_max_length-len(self.workers[i].identifier))} "
                    for k in self.time_units_indexes:
                        symbol = " "
                        for j in self.tasks_indexes:
                            if self.working_variables[i,j,k].solution_value() > 0.5:
                                symbol = self.tasks[j].symbol
                                break
                        msg += symbol
                    print(f"{msg}\n")
        else:
            raise Error(ErrorTypes.NOT_SOLVED_PROBLEM)

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
