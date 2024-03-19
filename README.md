# sweiot-channel-monitor
A tool to monitor channels of snaps

# How to Add a snap to be monitor and trigger a build job
1. If you need snaps info from store please add your snap name and store ID to the snaps.yaml
2. Please add the snap you want to monitor and the projects this snap would affect also build job to monitor.yaml
3. the device.yaml is a list that which project has what device can be used. But currently we haven't implment this part yet.

# How to Run the monitor
1. Please add snap.yaml to your workspace
example:

<snap name>:
  arch: <arm64/armhf/x86>
  store: <store ID>

<snap name>:
  arch: <arm64/armhf/x86>
  store: <store ID>


2. please add monitor.yaml to your workspace
example:

- <part name>:
    arch: arm64/armhf/x86
    channel: stable/candidate/beta/edge
    name: <snap name>
    jira_id: <epic card ID>
    projects:
      -  name: <project name>
         assignee: <mail of assignee>
         job: <jenkins job name>

3. Then You only have to run "python3 monitor.py" in your work folder

