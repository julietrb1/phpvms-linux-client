# phpVMS PIREP State Machine Explanation

Based on the phpVMS codebase analysis, here's how the PIREP (Pilot Report) state machine works:

## PIREP States vs Status

phpVMS uses two separate concepts:

### **PirepState** (Workflow States)
- `DRAFT = 5` - Initial creation, not yet submitted
- `IN_PROGRESS = 0` - Flight is ongoing (prefile state)
- `PENDING = 1` - Submitted, waiting for admin approval
- `ACCEPTED = 2` - Approved by admin
- `REJECTED = 6` - Rejected by admin
- `CANCELLED = 3` - Cancelled by pilot or admin
- `DELETED = 4` - Soft deleted
- `PAUSED = 7` - Flight paused

### **PirepStatus** (Flight Phase)
These correspond to actual flight phases and ACARS states:
- `INITIATED = 'INI'` - Flight initialized
- `SCHEDULED = 'SCH'` - Scheduled
- `BOARDING = 'BST'` - Boarding passengers
- `RDY_START = 'RDT'` - Ready to start
- `PUSHBACK_TOW = 'PBT'` - Pushback/tow
- `DEPARTED = 'OFB'` - Off block
- `TAXI = 'TXI'` - Taxiing
- `TAKEOFF = 'TOF'` - Taking off
- `AIRBORNE = 'TKO'` - Airborne
- `ENROUTE = 'ENR'` - En route
- `APPROACH = 'TEN'` - On approach
- `LANDING = 'LDG'` - Landing
- `LANDED = 'LAN'` - Landed
- `ON_BLOCK = 'ONB'` - On block
- `ARRIVED = 'ARR'` - Arrived
- `CANCELLED = 'DX'` - Cancelled
- `DIVERTED = 'DV'` - Diverted
- `PAUSED = 'PSD'` - Paused

## Normal Workflow Order

### 1. **PREFILE** (`PirepService::prefile()`)
**Trigger**: API call to `/api/v1/pireps/prefile`
- **Initial State**: `IN_PROGRESS`
- **Initial Status**: `INITIATED`
- **Purpose**: Create a new PIREP and reserve aircraft
- **Validations**:
  - User permissions and location
  - Aircraft availability and location
  - Airport existence
  - Duplicate detection
- **Actions**:
  - Create PIREP record
  - Link to SimBrief if provided
  - Set custom fields and fares

### 2. **UPDATE** (`PirepService::update()`)
**Trigger**: API call to `/api/v1/pireps/{id}` (PUT)
- **State**: Remains `IN_PROGRESS`
- **Status**: Can change based on flight phase
- **Purpose**: Update PIREP during flight
- **Actions**:
  - Update PIREP attributes
  - Update custom fields and fares
  - Validate aircraft permissions

### 3. **FILE** (`PirepService::file()`)
**Trigger**: API call to `/api/v1/pireps/{id}/file`
- **State**: Changes to `PENDING`
- **Status**: Set to `ARRIVED`
- **Purpose**: Submit completed flight for review
- **Actions**:
  - Set submission timestamp
  - Copy planned data from flight/SimBrief
  - Finalize SimBrief attachment
  - Save route if not already present

### 4. **SUBMIT** (`PirepService::submit()`)
**Trigger**: Called automatically after filing or manually
- **State**: Determined by rank settings:
  - `ACCEPTED` if auto-approval enabled
  - `PENDING` if manual approval required
- **Purpose**: Process the submitted PIREP
- **Logic**:
  ```php
  if ($pirep->source === PirepSource::ACARS && $pirep->user->rank->auto_approve_acars) {
      $state = PirepState::ACCEPTED;
  } elseif ($pirep->source === PirepSource::MANUAL && $pirep->user->rank->auto_approve_manual) {
      $state = PirepState::ACCEPTED;
  } else {
      $state = PirepState::PENDING;
  }
  ```

### 5. **ACCEPT** (`PirepService::accept()`)
**Trigger**: Admin approval or auto-approval
- **State**: `ACCEPTED`
- **Purpose**: Finalize successful flight
- **Actions**:
  - Update pilot statistics (flight time, flight count)
  - Calculate pilot rank
  - Update aircraft (location, flight time, fuel)
  - Set pilot location
  - Trigger financial calculations
  - Process awards

### 6. **REJECT** (`PirepService::reject()`)
**Trigger**: Admin rejection
- **State**: `REJECTED`
- **Purpose**: Reject the flight
- **Actions**:
  - If previously accepted, reverse statistics
  - Reverse aircraft updates
  - Recalculate pilot rank

## State Transition Rules

### **Read-Only States**
PIREPs cannot be modified when in these states:
```php
public static $read_only_states = [
    PirepState::ACCEPTED,
    PirepState::REJECTED,
    PirepState::CANCELLED,
];
```

### **Cancellation Rules**
PIREPs cannot be cancelled when in these states:
```php
public static $cancel_states = [
    PirepState::ACCEPTED,
    PirepState::REJECTED,
    PirepState::CANCELLED,
    PirepState::DELETED,
];
```

### **Valid State Transitions**
The `changeState()` method handles these transitions:
- `PENDING` → `ACCEPTED` or `REJECTED`
- `ACCEPTED` → `REJECTED` (with stat reversal)
- `REJECTED` → `ACCEPTED` (with stat application)

## Non-Happy Paths

### **Cancellation** (`PirepService::cancel()`)
**Trigger**: API call to `/api/v1/pireps/{id}/cancel`
- **Allowed From**: `IN_PROGRESS`, `PENDING`, `DRAFT`, `PAUSED`
- **Final State**: `CANCELLED`
- **Final Status**: `CANCELLED`
- **Actions**:
  - Set cancelled state and status
  - Trigger cancellation events
  - Release aircraft if reserved

### **Deletion** (`PirepService::delete()`)
**Trigger**: Admin action (force delete)
- **Actions**:
  - Remove all related data (comments, fares, fields, ACARS)
  - Update user's last PIREP reference
  - Force delete PIREP record

### **Diversion Handling** (`PirepService::handleDiversion()`)
**Trigger**: PIREP field indicates diversion airport
- **Actions**:
  - Update aircraft and pilot location to diversion airport
  - Create repositioning flight if needed
  - Update PIREP details
  - Remove flight relationship

### **Duplicate Detection**
**Trigger**: During prefile
- **Logic**: Checks for same user, airline, flight number, route within time window
- **Action**: Returns existing PIREP instead of creating new one

## ACARS Integration

### **Status Updates**
ACARS can update the `status` field during flight:
- Position updates via `/api/v1/acars/{id}/position`
- Log entries via `/api/v1/acars/{id}/logs`
- Events via `/api/v1/acars/{id}/events`

### **Status Progression**
Typical ACARS status progression:
```
INITIATED → BOARDING → RDY_START → PUSHBACK_TOW → DEPARTED → 
TAXI → TAKEOFF → AIRBORNE → ENROUTE → APPROACH → LANDING → 
LANDED → ON_BLOCK → ARRIVED
```

## Implementation for Python UI Client

### **State Machine Monitoring**
```python
class PirepStateMachine:
    def can_update(self, pirep_state):
        read_only_states = [2, 6, 3]  # ACCEPTED, REJECTED, CANCELLED
        return pirep_state not in read_only_states
    
    def can_cancel(self, pirep_state):
        cancel_states = [2, 6, 3, 4]  # ACCEPTED, REJECTED, CANCELLED, DELETED
        return pirep_state not in cancel_states
    
    def get_available_actions(self, pirep_state):
        actions = []
        if pirep_state == 0:  # IN_PROGRESS
            actions.extend(['update', 'file', 'cancel'])
        elif pirep_state == 1:  # PENDING
            actions.extend(['accept', 'reject'])  # Admin only
        elif pirep_state == 5:  # DRAFT
            actions.extend(['update', 'file', 'cancel'])
        return actions
```

### **UI State Indicators**
```python
def get_state_display(pirep_state, pirep_status):
    state_names = {
        0: "In Progress",
        1: "Pending Review", 
        2: "Accepted",
        3: "Cancelled",
        5: "Draft",
        6: "Rejected",
        7: "Paused"
    }
    
    status_names = {
        'INI': "Initialized",
        'ENR': "En Route", 
        'ARR': "Arrived",
        'DX': "Cancelled"
        # ... etc
    }
    
    return f"{state_names.get(pirep_state, 'Unknown')} ({status_names.get(pirep_status, pirep_status)})"
```

### **Workflow Implementation**
```python
class PirepWorkflow:
    def __init__(self, api_client):
        self.client = api_client
    
    async def create_flight(self, flight_data):
        # 1. Prefile
        pirep = await self.client.prefile_pirep(flight_data)
        
        # 2. Update during flight (multiple calls)
        # await self.client.update_pirep(pirep_id, updates)
        
        # 3. File when complete
        final_pirep = await self.client.file_pirep(pirep_id, final_data)
        
        return final_pirep
```

This state machine provides a robust workflow for flight operations while maintaining data integrity and proper audit trails throughout the flight lifecycle.