# Deadlocks

## What a deadlock is
A deadlock is a situation where a set of processes are each waiting for a resource held by another process in the set, so none can ever proceed. A deadlock needs all four Coffman conditions to hold at once: mutual exclusion (a resource is held by one process at a time), hold and wait (a process holds resources while waiting for more), no preemption (resources cannot be forcibly taken away) and circular wait (a closed chain of processes each waiting for the next).

## Resource allocation graph
In a resource allocation graph, a request edge goes from a process to a resource and an assignment edge goes from a resource to a process. If every resource type has a single instance, a cycle means deadlock. With multiple instances per resource, a cycle is necessary but not sufficient for deadlock.

## Deadlock prevention
Prevention makes sure at least one Coffman condition can never hold. Mutual exclusion cannot usually be removed for non-sharable resources. Hold and wait is broken by requiring a process to request all resources at once or to release everything before requesting more, which lowers utilisation and risks starvation. No preemption is broken by letting the system take resources from a waiting process. Circular wait is broken by imposing a total order on resource types and requiring requests in increasing order, which is the most practical technique.

## Deadlock avoidance and safe state
Avoidance uses advance information about maximum needs. A state is safe if there is some order of the processes, a safe sequence, in which each can obtain its maximum remaining need and finish. An unsafe state is not necessarily a deadlock, but it may lead to one, so the system only grants a request if the resulting state is safe.

## Banker's algorithm
The Banker's algorithm keeps Available (free units of each resource), Max (maximum demand), Allocation (currently held) and Need = Max - Allocation. The safety algorithm sets Work = Available, then repeatedly finds a process whose Need is less than or equal to Work, adds its Allocation to Work and marks it finished. If every process finishes, the state is safe. For a resource request, the system checks Request <= Need and Request <= Available, pretends to allocate it and runs the safety algorithm, granting it only if the state stays safe. Its cost is O(m * n squared) for n processes and m resource types.

## Banker's worked example
With five processes and resource types A, B, C, take Allocation P0=(0,1,0), P1=(2,0,0), P2=(3,0,2), P3=(2,1,1), P4=(0,0,2), Max P0=(7,5,3), P1=(3,2,2), P2=(9,0,2), P3=(2,2,2), P4=(4,3,3) and Available=(3,3,2). Need is P0=(7,4,3), P1=(1,2,2), P2=(6,0,0), P3=(0,1,1), P4=(4,3,1). The state is safe with the safe sequence P1, P3, P4, P0, P2.

## Deadlock detection and recovery
When avoidance is not used, the system can let deadlocks happen and detect them. With single-instance resources it searches the wait-for graph for a cycle. With multiple instances it runs an algorithm like the safety algorithm using current Requests instead of Need; processes that cannot finish are deadlocked. Recovery either terminates processes (all deadlocked ones, or one at a time choosing a victim by priority and work done) or preempts resources from victims and rolls them back, taking care to avoid starving the same victim. Many general-purpose systems simply ignore deadlocks (the ostrich approach) because they are rare and prevention is costly.
